"""
backend/app/agents/researcher.py
投研分析 Agent - 股票基本面分析、财务解读
"""
from typing import Dict, Any
from app.agents.base import BaseAgent, AgentConfig, AgentExecutionResult
from app.models.schemas import AgentType
from langchain.tools import tool
import json
from app.market import data as market
from app.market import insights, disclosures


def encode(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


@tool(description="查询真实A股公司信息，包含行业、上市日期及来源")
def get_stock_info(stock_code: str) -> str:
    return encode(market.stock_info(stock_code))


@tool(description="查询真实A股行情快照：价格、涨跌幅、PE(TTM)、PB、行情时间；可能延迟")
def get_stock_quote(stock_code: str) -> str:
    return encode(market.stock_quote(stock_code))


@tool(description="查询上证、深证成指、创业板指数的真实行情与时间，分析当前市场时使用")
def get_market_overview() -> str:
    return encode(market.market_overview())


@tool(description="查询真实财报：annual年报，quarterly各报告期累计值；含披露日期、金额元、比率百分数")
def get_stock_financials(stock_code: str, period: str = "annual") -> str:
    return encode(market.stock_financials(stock_code, period))


@tool(description="查询真实前复权日线OHLCV，days为2–500个交易日，成交量单位手")
def get_stock_kline(stock_code: str, days: int = 60) -> str:
    return encode(market.stock_kline(stock_code, days))


@tool(description="检索东方财富财经新闻，返回来源、日期、链接和摘要；不代表完整事件核查")
def search_financial_news(keyword: str, limit: int = 10) -> str:
    return encode(market.financial_news(keyword, limit))


@tool(description="查询个股或沪深市场资金流，stock_code留空为市场；包含1/5/10/20日主力净流入汇总，金额元，非北向净买入")
def get_fund_flow(stock_code: str = "", days: int = 60) -> str:
    result = insights.fund_flow(stock_code or None, days)
    result['data'] = result['data'][-10:]
    result['tool_note'] = '工具仅展示最近10日明细和窗口汇总，完整请求序列可通过对应数据API查询。'
    return encode(result)


@tool(description="查询沪深京融资融券余额、融资买入/偿还/净买入，金额元；数据通常延迟一天")
def get_margin_data(days: int = 20) -> str:
    return encode(insights.margin_history(days))


@tool(description="查询北向成交总额历史；2024-08-19以后每日净买入不再公开，返回null，不得将成交额解释成净流入")
def get_northbound_data(days: int = 20) -> str:
    return encode(insights.northbound_history(days))


@tool(description="比较行业industry或概念concept板块相邻两个5交易日窗口的收益、资金与排名变化；含覆盖数量及来源，limit为1–100")
def get_sector_rotation(sector_type: str = "industry", limit: int = 8) -> str:
    result = insights.sector_rotation(sector_type, limit)
    result.pop('data')
    result['tool_note'] = '排名基于coverage所示集合，工具仅展示领先、改善、走弱列表；API返回全部板块明细。'
    return encode(result)


@tool(description="用实际历史PE(TTM)/PB(MRQ)序列计算估值分位，years支持1/3/5/10；含样本数、排除数、实际起止日期和算法")
def get_valuation_percentiles(stock_code: str, years: int = 3) -> str:
    result = insights.valuation_percentiles(stock_code, years)
    result['recent_observations'] = result.pop('data')[-5:]
    result['tool_note'] = '分位用完整已获取序列计算，工具仅展示最近5日明细；API返回完整序列。'
    return encode(result)


@tool(description="检索巨潮公司公告中监管、处罚、诉讼、仲裁、执行等标题，默认近3年；保留原文链接与分页覆盖，start_page用于续查")
def check_regulatory_events(stock_code: str, start_date: str = "", end_date: str = "", start_page: int = 1) -> str:
    return encode(disclosures.regulatory_events(stock_code, start_date or None, end_date or None, start_page))


@tool(description="读取巨潮公告原文PDF并保留页码；document_url必须来自公告检索结果，用于确认事件主体、阶段、金额及结论")
def read_announcement(document_url: str) -> str:
    return encode(disclosures.announcement_content(document_url))


RESEARCHER_SYSTEM_PROMPT = market.DATA_POLICY + """
涉及当前市场时先调用 get_market_overview；个股判断先获取报价、财报与日线。
涉及资金面调用 get_fund_flow、get_margin_data 和 get_northbound_data；轮动调用 get_sector_rotation；估值历史位置必须调用 get_valuation_percentiles；监管诉讼调用 check_regulatory_events 并读取相关公告原文。
你是资深金融投研分析师，10年+经验，擅⻓基本面分析、财务建模。

分析框架：
- **业绩驱动因素**：营收增⻓来源、市场份额变化
- **盈利能力分析**：毛利率、净利率、ROE 趋势
- **估值判断**：PE/PB/PS 横向（vs 行业）和纵向（vs 历史）对比
- **⻛险提示**：经营⻛险、财务⻛险、行业周期性
- **投资建议**：客观结论

输出：Markdown结构，数据有来源，关键结论**加粗**，⻛险⚠开头"""


class ResearcherAgent(BaseAgent):
    def __init__(self):
        tools = [get_stock_info, get_stock_quote, get_market_overview, get_stock_financials, get_stock_kline, search_financial_news,
                 get_fund_flow, get_margin_data, get_northbound_data, get_sector_rotation,
                 get_valuation_percentiles, check_regulatory_events, read_announcement]
        config = AgentConfig(
            name="投研分析Agent", agent_type=AgentType.RESEARCHER,
            description="股票基本面分析、财务解读",
            system_prompt=RESEARCHER_SYSTEM_PROMPT, tools=tools, max_iterations=8,
        )
        super().__init__(config)

    def _build_system_prompt(self) -> str:
        return self.config.system_prompt

    def _parse_output(self, raw_output: str) -> Dict[str, Any]:
        return {"analysis": raw_output, "agent_type": "researcher"}

    async def analyze_stock(self, stock_code: str, query: str = "") -> AgentExecutionResult:
        task = f"分析股票 {stock_code}。获取基本信息、财务数据，进行估值分析，对比行业，输出综合研判。{query}"
        return await self.execute(task=task)
