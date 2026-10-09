"""Auditable flow, sector rotation and historical valuation data from Eastmoney."""
import time
import requests
from datetime import datetime, timedelta

from app.market.data import MarketDataError, SHANGHAI, envelope, number, payload, request, symbol

DATACENTER = 'https://datacenter-web.eastmoney.com/api/data/v1/get'
FLOW_NOTE = ('主力=供应商按成交单大小归类的大单与超大单；属于成交方向估算，'
             '不是账户资金进出、机构真实持仓或北向净买入。金额元，比率%。')
NORTH_POLICY_URL = 'https://investor.szse.cn/szhk/hkbussiness/news/t20240726_608353.html'



def quote_request(url, params):
    # Eastmoney push endpoints disconnect with httpx on this network; the
    # standard requests transport is verified against the same public URLs.
    try:
        response = requests.get(url, params=params, timeout=8)
        response.raise_for_status()
        return response
    except requests.RequestException as exc:
        raise MarketDataError('东方财富资金/板块接口不可用，请稍后重试；不使用模拟数据') from exc


def date_value(value):
    return datetime.strptime(str(value)[:10], '%Y-%m-%d').date().isoformat()


def dated_rows(rows, field='date'):
    rows.sort(key=lambda r: r[field])
    if len({r[field] for r in rows}) != len(rows):
        raise MarketDataError('上游时间序列存在重复日期，无法可靠计算')
    if rows and rows[-1][field] > datetime.now(SHANGHAI).date().isoformat():
        raise MarketDataError('上游数据日期在未来')
    return rows


def freshness(as_of):
    if as_of and as_of[:10] < datetime.now(SHANGHAI).date().isoformat():
        return ['数据日期早于今天（可能休市或披露延迟），不可称为今日实时数据。']
    return []


def datacenter(report, params):
    response = request(DATACENTER, {'reportName': report, 'columns': 'ALL', **params})
    body = payload(response)
    result = body.get('result')
    if not body.get('success') or not isinstance(result, dict) or not isinstance(result.get('data'), list):
        raise MarketDataError(f'{report} 未返回有效数据，不能视为零记录')
    return result, str(response.url)


def fund_flow(stock_code=None, days=60):
    if not 1 <= days <= 120:
        raise MarketDataError('days 必须在 1–120 个交易日之间')
    params = dict(lmt=days, klt=101, fields1='f1,f2,f3,f7',
        fields2=','.join(f'f{i}' for i in range(51, 66)), ut='b2884a393a59ad64002292a3e90d46a5')
    if stock_code:
        ticker = symbol(stock_code)
        params['secid'] = ('1.' if ticker.startswith('sh') else '0.') + stock_code
    else:
        params.update(secid='1.000001', secid2='0.399001')
    response = quote_request('https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get', params)
    item = payload(response).get('data') or {}
    if stock_code and item.get('code') != stock_code:
        raise MarketDataError('资金流证券代码不匹配')
    rows = []
    fields = ['main_net_cny', 'small_net_cny', 'medium_net_cny', 'large_net_cny', 'super_large_net_cny',
              'main_net_pct', 'small_net_pct', 'medium_net_pct', 'large_net_pct', 'super_large_net_pct']
    for line in item.get('klines') or []:
        values = line.split(',')
        if len(values) < 15:
            raise MarketDataError('资金流字段不完整')
        row = {'date': date_value(values[0]), **{f: number(v) for f, v in zip(fields, values[1:11])}}
        rows.append(row)
    dated_rows(rows)
    rows = rows[-days:]
    if not rows or all(r['main_net_cny'] is None for r in rows):
        raise MarketDataError('没有有效资金流数据')
    summaries = {}
    for window in (1, 5, 10, 20):
        sample = rows[-window:]
        valid = len(sample) == window and all(r['main_net_cny'] is not None for r in sample)
        summaries[f'{window}d'] = dict(samples=len(sample), complete=valid,
            start_date=sample[0]['date'], end_date=sample[-1]['date'],
            main_net_cny=sum(r['main_net_cny'] for r in sample) if valid else None)
    warnings = [FLOW_NOTE, '盘中当日统计尚未完成，历史可用长度由供应商决定。'] + freshness(rows[-1]['date'])
    if len(rows) < days:
        warnings.append(f'仅返回 {len(rows)} 个交易日，少于请求的 {days} 日。')
    return envelope('东方财富资金流', str(response.url), rows, rows[-1]['date'], warnings) | {
        'code': stock_code, 'scope': '个股' if stock_code else '沪深市场（不含北交所）',
        'summaries': summaries, 'requested_days': days, 'samples': len(rows)}


def margin_history(days=20):
    if not 1 <= days <= 120:
        raise MarketDataError('days 必须在 1–120 之间')
    result, url = datacenter('RPTA_WEB_RZRQ_LSSH', dict(pageNumber=1, pageSize=days * 3,
        sortColumns='DIM_DATE,SCDM', sortTypes='-1,1'))
    markets = {'007': '上海', '001': '深圳', '002': '北京'}
    data = []
    seen = set()
    for row in result['data']:
        if row['SCDM'] not in markets:
            continue
        date = date_value(row['DIM_DATE'])
        key = (date, row['SCDM'])
        if key in seen:
            raise MarketDataError('两融记录日期/市场重复')
        seen.add(key)
        data.append(dict(date=date, market=markets[row['SCDM']],
            financing_balance_cny=number(row.get('RZYE')), short_balance_cny=number(row.get('RQYE')),
            total_balance_cny=number(row.get('RZRQYE')), financing_buy_cny=number(row.get('RZMRE')),
            financing_repay_cny=number(row.get('RZCHE')), financing_net_buy_cny=number(row.get('RZJME'))))
    if not data:
        raise MarketDataError('两融统计没有有效记录')
    data.sort(key=lambda r: (r['date'], r['market']))
    latest = data[-1]['date']
    current = [r for r in data if r['date'] == latest]
    complete = {r['market'] for r in current} == set(markets.values())
    valid = complete and all(r['total_balance_cny'] is not None for r in current)
    return envelope('东方财富（交易所两融统计）', url, data, latest,
        ['金额元；余额是存量，融资净买入是流量；交易所数据通常晚于行情披露。'] + freshness(latest)) | {
        'latest_markets_complete': complete,
        'latest_total_balance_cny': sum(r['total_balance_cny'] for r in current) if valid else None}


def northbound_history(days=20):
    if not 1 <= days <= 120:
        raise MarketDataError('days 必须在 1–120 之间')
    result, url = datacenter('RPT_MUTUAL_DEAL_HISTORY', dict(pageNumber=1, pageSize=days,
        sortColumns='TRADE_DATE', sortTypes=-1, filter='(MUTUAL_TYPE="005")'))
    data = []
    for row in result['data']:
        if row.get('MUTUAL_TYPE') != '005':
            raise MarketDataError('北向数据类型不匹配，不能混入南向成交')
        date = date_value(row['TRADE_DATE'])
        def amount(key):
            value = number(row.get(key))
            return value * 1_000_000 if value is not None else None
        changed = date >= '2024-08-19'
        data.append(dict(date=date, turnover_cny=amount('DEAL_AMT'),
            buy_cny=None if changed else amount('BUY_AMT'), sell_cny=None if changed else amount('SELL_AMT'),
            net_buy_cny=None if changed else amount('NET_DEAL_AMT'),
            net_buy_status='not_disclosed' if changed else 'historical_disclosure'))
    dated_rows(data)
    if not data:
        raise MarketDataError('没有北向成交披露记录')
    return envelope('东方财富沪深港通披露汇总', url, data, data[-1]['date'],
        ['金额由供应商百万元转换为元；成交总额不等于净买入。',
         '2024-08-19 起不再公开每日北向买入/卖出/净买入，此后字段固定为 null，不使用供应商估算补位。']
        + freshness(data[-1]['date'])) | {'disclosure_policy_url': NORTH_POLICY_URL}


def sector_rotation(sector_type='industry', limit=15):
    if sector_type not in ('industry', 'concept') or not 1 <= limit <= 100:
        raise MarketDataError('sector_type 为 industry/concept，limit 为 1–100')
    url = 'https://push2.eastmoney.com/api/qt/clist/get'
    params = dict(pn=1, pz=100, po=1, np=1, fltt=2, invt=2,
        fs='m:90 t:' + ('2' if sector_type == 'industry' else '3'), fid='f12',
        fields='f12,f14,f3,f62,f109,f164,f160,f174,f124', ut='b2884a393a59ad64002292a3e90d46a5')
    rows, urls, warnings = [], [], [FLOW_NOTE, '板块可能存在层级重叠，不能把各板块资金相加视为全市场资金。']
    expected, complete = None, True
    started = time.monotonic()
    for page in range(1, 21):
        if time.monotonic() - started > 18:
            complete = False
            warnings.append('分页查询达到时间上限，仅分析已返回板块。')
            break
        response = quote_request(url, params | {'pn': page})
        body = payload(response).get('data')
        if not isinstance(body, dict) or not isinstance(body.get('diff'), list):
            raise MarketDataError('板块列表响应异常，无法排名')
        total = int(body['total'])
        expected = total if expected is None else expected
        if total != expected:
            complete = False
            warnings.append('分页过程中板块总数改变，排名覆盖不完整。')
        urls.append(str(response.url))
        rows.extend(body['diff'])
        if len(rows) >= expected or not body['diff']:
            break
    by_code = {row['f12']: row for row in rows}
    complete = complete and len(by_code) == expected and len(rows) == len(by_code)
    if not by_code:
        raise MarketDataError('未取得板块数据')
    data = []
    for row in by_code.values():
        r5, r10 = number(row.get('f109')), number(row.get('f160'))
        f5, f10 = number(row.get('f164')), number(row.get('f174'))
        stamp = number(row.get('f124'))
        data.append(dict(code=row['f12'], name=row['f14'],
            as_of=datetime.fromtimestamp(stamp, SHANGHAI).isoformat() if stamp else None,
            return_1d_pct=number(row.get('f3')), return_5d_pct=r5, return_10d_pct=r10,
            previous_5d_return_pct=((1 + r10 / 100) / (1 + r5 / 100) - 1) * 100
                if r5 is not None and r10 is not None and r5 > -100 else None,
            main_net_1d_cny=number(row.get('f62')), main_net_5d_cny=f5, main_net_10d_cny=f10,
            previous_5d_main_net_cny=f10 - f5 if f5 is not None and f10 is not None else None))
    dates = {r['as_of'][:10] for r in data if r['as_of']}
    aligned = len(dates) == 1 and all(r['as_of'] for r in data)
    if not aligned:
        warnings.append('部分板块时间缺失或交易日期不一致，不能比较轮动排名。')
    eligible = [r for r in data if r['return_5d_pct'] is not None and r['previous_5d_return_pct'] is not None]
    if not eligible:
        raise MarketDataError('缺少可比较的 5/10 日板块收益')
    if aligned:
        # Competition ranks preserve ties. Both periods use the same eligible universe.
        for value_key, rank_key in [('return_5d_pct', 'rank_recent_5d'), ('previous_5d_return_pct', 'rank_previous_5d')]:
            ordered = sorted(eligible, key=lambda r: r[value_key], reverse=True)
            rank, previous = 0, None
            for index, row in enumerate(ordered, 1):
                if previous is None or row[value_key] != previous:
                    rank = index
                row[rank_key] = rank
                previous = row[value_key]
        for row in eligible:
            row['rank_improvement'] = row['rank_previous_5d'] - row['rank_recent_5d']
    ranked = sorted(eligible, key=lambda r: r.get('rank_improvement', 0), reverse=True)
    as_of = max((r['as_of'] for r in data if r['as_of']), default=None)
    return envelope('东方财富板块行情/资金流', urls[0], data, as_of, warnings + freshness(as_of)) | {
        'status': 'ok' if complete and aligned else 'partial', 'source_urls': urls,
        'sector_type': sector_type, 'coverage': dict(total=expected, fetched=len(data),
            comparable=len(eligible), complete=complete, dates_aligned=aligned),
        'leaders': sorted(eligible, key=lambda r: r['return_5d_pct'], reverse=True)[:limit],
        'improving': [r for r in ranked if r.get('rank_improvement', 0) > 0][:limit],
        'weakening': sorted([r for r in ranked if r.get('rank_improvement', 0) < 0],
                           key=lambda r: r['rank_improvement'])[:limit],
        'method': '相邻不重叠的两个5交易日窗口；前5日收益=(1+10日收益)/(1+最近5日收益)-1；前5日资金=10日资金-最近5日资金。排名改善=前5日名次-最近5日名次，正数为改善。同值并列；仅在两个窗口都有数据的相同板块集合中排名，非历史成分回测。'}


def valuation_percentiles(stock_code, years=3):
    symbol(stock_code)
    if years not in (1, 3, 5, 10):
        raise MarketDataError('years 支持 1、3、5、10')
    today = datetime.now(SHANGHAI).date()
    try:
        start = today.replace(year=today.year - years)
    except ValueError:
        start = today.replace(year=today.year - years, day=28)
    params = dict(pageNumber=1, pageSize=500, sortColumns='TRADE_DATE', sortTypes=-1,
        filter=f'(SECURITY_CODE="{stock_code}")(TRADE_DATE>=\'{start}\')(TRADE_DATE<=\'{today}\')')
    data, urls = [], []
    pages, started = 1, time.monotonic()
    for page in range(1, 11):
        if time.monotonic() - started > 18:
            raise MarketDataError('估值历史分页未完成，请缩短窗口后重试；不计算不完整序列分位')
        result, url = datacenter('RPT_VALUEANALYSIS_DET', params | {'pageNumber': page})
        current_pages = int(result['pages'])
        if page > 1 and current_pages != pages:
            raise MarketDataError('估值分页数据发生变化，请重试')
        pages = current_pages
        urls.append(url)
        for row in result['data']:
            if row.get('SECURITY_CODE') != stock_code:
                raise MarketDataError('估值序列证券代码不匹配')
            date = date_value(row['TRADE_DATE'])
            if not str(start) <= date <= str(today):
                raise MarketDataError('估值序列日期不在请求范围')
            data.append(dict(date=date, pe_ttm=number(row.get('PE_TTM')), pb_mrq=number(row.get('PB_MRQ'))))
        if page >= pages:
            break
    if pages > len(urls):
        raise MarketDataError('估值分页不完整，不能计算历史分位')
    dated_rows(data)
    if not data:
        raise MarketDataError('估值历史没有有效记录')
    metrics = {}
    for field in ('pe_ttm', 'pb_mrq'):
        valid = [r[field] for r in data if r[field] is not None and r[field] > 0]
        current = data[-1][field]
        enough = len(valid) >= 60 and current is not None and current > 0
        metrics[field] = dict(current=current, samples=len(valid), excluded=len(data) - len(valid),
            percentile=100 * (sum(v < current for v in valid) + .5 * sum(v == current for v in valid)) / len(valid)
                if enough else None, status='ok' if enough else 'insufficient_or_nonpositive',
            min=min(valid) if valid else None, max=max(valid) if valid else None)
    warnings = ['只使用同一供应商的日频 PE(TTM)、PB(MRQ)；排除缺失/非正估值，不能将亏损期负PE当成低估。',
                '至少60个有效观测才计算分位；分位只描述所示历史样本，不代表未来收益。'] + freshness(data[-1]['date'])
    if data[0]['date'] > (start + timedelta(days=10)).isoformat():
        warnings.append('实际可用历史短于请求窗口（可能新股或数据源覆盖不足），不得称为完整窗口分位。')
    return envelope('东方财富历史估值', urls[0], data, data[-1]['date'], warnings) | {
        'code': stock_code, 'source_urls': urls, 'years': years, 'requested_start': str(start),
        'actual_start': data[0]['date'], 'actual_end': data[-1]['date'], 'observations': len(data),
        'metrics': metrics, 'method': '分位%=100×(小于当前值的样本数+0.5×等于当前值的样本数)/有效样本数；包含当前日。'}
