import json
from datetime import datetime, timedelta
from unittest.mock import Mock

import httpx
import pytest
from fastapi.testclient import TestClient

from app.market import data as market


def respond(monkeypatch, body, *, text=False):
    def get(url, params, **kwargs):
        request = httpx.Request('GET', url, params=params)
        return httpx.Response(200, request=request,
            **({'content': body.encode('gb18030')} if text else {'json': body}))
    mock = Mock(side_effect=get)
    monkeypatch.setattr(market.httpx, 'get', mock)
    return mock


def quote_text(price='123.45', timestamp='20261009150000'):
    fields = [''] * 48
    for i, value in {1: '测试公司', 2: '600519', 3: price, 4: '120', 5: '121',
                     6: '1000', 30: timestamp, 32: '2.875', 33: '125', 34: '120',
                     38: '0.1', 39: '15.2', 45: '100', 46: '3.2'}.items():
        fields[i] = value
    return 'v_sh600519="' + '~'.join(fields) + '";'


def test_quote_preserves_timestamp_units_and_missing_values(monkeypatch):
    respond(monkeypatch, quote_text(), text=True)
    result = market.stock_quote('600519')
    assert result['is_demo'] is False
    assert result['as_of'] == '2026-10-09T15:00:00+08:00'
    assert result['data']['name'] == '测试公司'
    assert result['data']['price'] == 123.45
    assert result['data']['volume_unit'] == '手'
    assert 'q=sh600519' in result['source_url']
    assert market.number('-') is None
    assert market.number('NaN') is None
    assert market.number('0') == 0


@pytest.mark.parametrize('price', ['0', '-', 'nan', '-1'])
def test_invalid_quote_never_becomes_a_success(monkeypatch, price):
    respond(monkeypatch, quote_text(price), text=True)
    with pytest.raises(market.MarketDataError):
        market.stock_quote('600519')


def test_stale_quote_is_explicit(monkeypatch):
    respond(monkeypatch, quote_text(timestamp='20200102150000'), text=True)
    assert any('早于今天' in w for w in market.stock_quote('600519')['warnings'])


@pytest.mark.parametrize('code', ['000001', '300750', '688001', '600519', '920001'])
def test_stock_symbol_mapping(code):
    assert market.symbol(code)[2:] == code
    assert market.symbol('000001') == 'sz000001'


def test_invalid_code_does_not_request_network(monkeypatch):
    mock = respond(monkeypatch, {})
    with pytest.raises(market.MarketDataError):
        market.stock_quote('sh600519&other=1')
    mock.assert_not_called()


def test_market_partial_results_do_not_invent_missing_indices(monkeypatch):
    monkeypatch.setattr(market, 'quotes', lambda _: {'sh000001': {'data': {'price': 4000}}})
    result = market.market_overview()
    assert result['status'] == 'partial'
    assert result['missing'] == ['sz399001', 'sz399006']


def test_kline_mapping_adjustment_and_rejection(monkeypatch):
    rows = [['2026-01-01', '10', '11', '12', '9', '100'],
            ['2026-01-02', '11', '10', '12', '9', '110']]
    respond(monkeypatch, {'data': {'sh600519': {'qfqday': rows}}})
    result = market.stock_kline('600519', 2)
    assert result['data'][0]['close'] == 11
    assert result['adjustment'] == 'qfq'
    rows[1][3] = '0'
    with pytest.raises(market.MarketDataError):
        market.stock_kline('600519', 2)
    respond(monkeypatch, {'data': {'sh600519': {'day': rows}}})
    with pytest.raises(market.MarketDataError):
        market.stock_kline('600519', 2)


def test_financial_periods_nulls_and_disclosure(monkeypatch):
    rows = [dict(SECURITY_CODE='600519', REPORT_DATE='2025-06-30', NOTICE_DATE='2025-08-01',
                 TOTALOPERATEREVE=100, PARENTNETPROFIT=-10, ROEJQ=None, CURRENCY='CNY'),
            dict(SECURITY_CODE='600519', REPORT_DATE='2024-12-31', NOTICE_DATE='2025-03-01',
                 TOTALOPERATEREVE=200, PARENTNETPROFIT=0, ROEJQ=0, CURRENCY='CNY')]
    respond(monkeypatch, {'result': {'data': rows}})
    annual = market.stock_financials('600519')
    assert len(annual['data']) == 1
    assert annual['data'][0]['net_profit'] == 0
    assert annual['as_of'] == '2024-12-31'
    quarterly = market.stock_financials('600519', 'quarterly')
    assert quarterly['data'][0]['roe_pct'] is None
    assert quarterly['data'][0]['net_profit'] == -10
    assert quarterly['data'][0]['disclosure_date'] == '2025-08-01'


def test_news_preserves_links_and_removes_markup(monkeypatch):
    body = {'result': {'cmsArticleWebOld': [dict(title='<em>公司</em>公告', content='摘要',
        date='2026-01-01', mediaName='来源', url='https://finance.eastmoney.com/a/1.html')]}}
    respond(monkeypatch, 'marketnews(' + json.dumps(body) + ')', text=True)
    result = market.financial_news('公司')
    assert result['data'][0]['title'] == '公司公告'
    assert result['data'][0]['url'].startswith('https://')
    respond(monkeypatch, 'marketnews({"result":{"cmsArticleWebOld":[]}})', text=True)
    assert market.financial_news('公司')['data'] == []


def test_risk_uses_real_return_math_and_aligned_beta(monkeypatch):
    rows = []
    close = 100
    for i in range(23):
        close *= 1.01 if i % 2 else .98
        rows.append(dict(date=(datetime(2025, 1, 1) + timedelta(days=i)).date().isoformat(), close=close))
    monkeypatch.setattr(market, 'stock_kline', lambda *a, **kw:
        market.envelope('fixture', 'https://example.com', rows, rows[-1]['date'] if rows else None))
    result = market.risk_metrics('600519', 20)['data']
    assert result['samples'] == 20
    assert result['var_95_loss'] == pytest.approx(.02)
    assert result['beta'] == pytest.approx(1)
    assert result['max_drawdown'] < 0
    assert result['annualized_volatility'] > 0
    rows.clear()
    with pytest.raises(market.MarketDataError, match='不足'):
        market.risk_metrics('600519', 20)


def test_api_and_tool_fail_explicitly_on_network_error(monkeypatch):
    from app.main import app
    from app.agents.researcher import get_stock_quote
    monkeypatch.setattr(market.httpx, 'get', Mock(side_effect=httpx.ConnectError('offline')))
    with pytest.raises(market.MarketDataError, match='未使用演示'):
        get_stock_quote.invoke({'stock_code': '600519'})
    response = TestClient(app).get('/api/v1/data/stock/600519/quote')
    assert response.status_code == 502
    assert '演示' in response.json()['detail']
    assert TestClient(app).post('/api/v1/data/pipeline/run').status_code == 501


def test_company_information_is_from_provider(monkeypatch):
    respond(monkeypatch, {'result': {'data': [dict(SECURITY_CODE='600519',
        SECURITY_NAME_ABBR='贵州茅台', EM2016='食品饮料-白酒', LISTING_DATE='2001-08-27 00:00:00')]}})
    result = market.stock_info('600519')
    assert result['data']['name'] == '贵州茅台'
    assert result['data']['listing_date'] == '2001-08-27'
    assert result['as_of'] is None
    respond(monkeypatch, {'result': {'data': []}})
    with pytest.raises(market.MarketDataError):
        market.stock_info('600519')


def test_risk_beta_failure_keeps_computed_metrics(monkeypatch):
    def history(*args, **kwargs):
        if kwargs.get('ticker'):
            raise market.MarketDataError('基准不可用')
        rows = [dict(date=(datetime(2025, 1, 1) + timedelta(days=i)).date().isoformat(),
                     close=100 + i) for i in range(22)]
        return market.envelope('fixture', 'https://example.com', rows)
    monkeypatch.setattr(market, 'stock_kline', history)
    result = market.risk_metrics('600519', 20)
    assert result['data']['beta'] is None
    assert result['data']['annualized_volatility'] > 0
    assert any('基准不可用' in warning for warning in result['warnings'])


def test_intraday_bar_is_excluded_from_risk(monkeypatch):
    class Morning(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 10, 9, 10, tzinfo=tz)
    monkeypatch.setattr(market, 'datetime', Morning)
    rows = [dict(date=(datetime(2026, 9, 18) + timedelta(days=i)).date().isoformat(),
                 close=100 + i) for i in range(22)]
    rows[-1]['close'] = 10000  # Today's incomplete bar must not enter returns.
    monkeypatch.setattr(market, 'stock_kline', lambda *a, **kw:
        market.envelope('fixture', 'https://example.com', rows))
    result = market.risk_metrics('600519', 20)['data']
    assert result['end_date'] == '2026-10-08'
    assert result['samples'] == 20
    assert result['annualized_volatility'] < .1
