"""
backend/app/agents/researcher.py
投研分析 Agent - 股票基本面分析、财务解读
"""
from typing import Dict, Any
from app.agents.base import BaseAgent, AgentConfig, AgentExecutionResult
from app.models.schemas import AgentType
from langchain.tools import tool


@tool(description="查询股票基本信息（代码、名称、行业、上市时间、市值等）")
def get_stock_info(stock_code: str) -> str:
    return f'{{"code": "{stock_code}", "name": "股票名称", "industry": "行业"}}'


@tool(description="查询股票财务数据（营收、净利润、毛利率、ROE等）")
def get_stock_financials(stock_code: str, period: str = "annual") -> str:
    return f'{{"code": "{stock_code}", "period": "{period}", "revenue": 0, "net_profit": 0, "roe": 0.0}}'


@tool(description="查询股票K线数据（OHLCV）")
def get_stock_kline(stock_code: str, days: int = 60) -> str:
    return f'[{{"date": "2024-01-01", "open": 0, "high": 0, "low": 0, "close": 0, "volume": 0}}]'


@tool(description="查询财经新闻")
def search_financial_news(keyword: str, limit: int = 10) -> str:
    return f'[{{"title": "新闻标题", "source": "来源", "date": "2024-01-01"}}]'


RESEARCHER_SYSTEM_PROMPT = """当前金融工具返回的是演示数据，不是真实行情。使用工具结果时必须明确标记为演示，不能据此给出真实投资结论。
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
        tools = [get_stock_info, get_stock_financials, get_stock_kline, search_financial_news]
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
