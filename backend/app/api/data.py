"""Financial data API backed by the same sources as the Agent tools."""
from fastapi import APIRouter, HTTPException, Query
from app.market import data as market
from app.market import insights, disclosures

router = APIRouter()


def query(func, *args):
    try:
        return func(*args)
    except (ValueError, KeyError, TypeError, IndexError) as exc:
        raise HTTPException(502, f'金融数据不可用：{exc}') from exc


@router.get('/data/market')
def get_market():
    return query(market.market_overview)


@router.get('/data/stock/{stock_code}')
def get_stock_info(stock_code: str):
    return query(market.stock_info, stock_code)


@router.get('/data/stock/{stock_code}/quote')
def get_stock_quote(stock_code: str):
    return query(market.stock_quote, stock_code)


@router.get('/data/stock/{stock_code}/kline')
def get_stock_kline(stock_code: str, days: int = Query(60, ge=2, le=500)):
    return query(market.stock_kline, stock_code, days)


@router.get('/data/stock/{stock_code}/financials')
def get_stock_financials(stock_code: str, period: str = 'annual'):
    return query(market.stock_financials, stock_code, period)


@router.get('/data/stock/{stock_code}/risk')
def get_stock_risk(stock_code: str, period: int = Query(60, ge=20, le=250)):
    return query(market.risk_metrics, stock_code, period)


@router.get('/data/news')
def get_news(keyword: str, limit: int = Query(10, ge=1, le=20)):
    return query(market.financial_news, keyword, limit)


@router.post('/data/pipeline/run')
def run_data_pipeline(pipeline_name: str = 'stock_quote'):
    raise HTTPException(501, '持久化数据管道尚未接入，请使用金融数据查询接口；不返回模拟成功')


@router.get('/data/fund-flow')
def get_market_fund_flow(days: int = Query(60, ge=1, le=120)):
    return query(insights.fund_flow, None, days)


@router.get('/data/stock/{stock_code}/fund-flow')
def get_stock_fund_flow(stock_code: str, days: int = Query(60, ge=1, le=120)):
    return query(insights.fund_flow, stock_code, days)


@router.get('/data/margin')
def get_margin_data(days: int = Query(20, ge=1, le=120)):
    return query(insights.margin_history, days)


@router.get('/data/northbound')
def get_northbound_data(days: int = Query(20, ge=1, le=120)):
    return query(insights.northbound_history, days)


@router.get('/data/sectors/rotation')
def get_sector_rotation(sector_type: str = 'industry', limit: int = Query(15, ge=1, le=100)):
    return query(insights.sector_rotation, sector_type, limit)


@router.get('/data/stock/{stock_code}/valuation')
def get_valuation(stock_code: str, years: int = 3):
    return query(insights.valuation_percentiles, stock_code, years)


@router.get('/data/stock/{stock_code}/regulatory-events')
def get_regulatory_events(stock_code: str, start_date: str | None = None,
                          end_date: str | None = None, start_page: int = Query(1, ge=1, le=1000)):
    return query(disclosures.regulatory_events, stock_code, start_date, end_date, start_page)


@router.get('/data/announcements/content')
def get_announcement_content(document_url: str):
    return query(disclosures.announcement_content, document_url)
