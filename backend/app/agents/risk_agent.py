"""
backend/app/agents/risk_agent.py
⻛控预警 Agent - ⻛险识别、量化评估、预警
"""
from typing import Dict, Any
from app.agents.base import BaseAgent, AgentConfig, AgentExecutionResult
from app.models.schemas import AgentType
from langchain.tools import tool
import json
from app.market import data as market
from app.market import disclosures


@tool(description="计算股票⻛险指标（波动率、VaR、Beta等）")
def calculate_risk_metrics(stock_code: str, period: int = 60) -> str:
    return json.dumps(market.risk_metrics(stock_code, period), ensure_ascii=False, allow_nan=False)


@tool(description="检索巨潮公司监管/诉讼公告标题，默认近3年；返回原文链接、日期和覆盖情况，start_page用于续查")
def check_regulatory_events(stock_code: str, start_date: str = "", end_date: str = "", start_page: int = 1) -> str:
    return json.dumps(disclosures.regulatory_events(stock_code, start_date or None, end_date or None, start_page), ensure_ascii=False)


@tool(description="读取公告检索返回的巨潮PDF原文，核实主体、诉讼阶段、处罚结果与金额；保留页码")
def read_announcement(document_url: str) -> str:
    return json.dumps(disclosures.announcement_content(document_url), ensure_ascii=False)


RISK_AGENT_SYSTEM_PROMPT = market.DATA_POLICY + """
风险指标单位为小数收益率；样本不足不得给出量化评分。
监管与诉讼检索返回标题线索后，应读取相关公告原文；若无法读到原文，仅列线索，不断言具体违法、胜败诉或处罚金额。
你是专业金融⻛控专家，擅⻓⻛险量化、预警模型、合规审查。

⻛控框架：
- 财务⻛险：盈利质量、现金流异常、债务结构
- 经营⻛险：大客戶依赖、竞争壁垒、管理层变更
- 市场⻛险：波动性、VaR、Beta、系统性⻛险
- 合规⻛险：监管处罚、信息披露违规

⻛险评分：
- 红色 高⻛险（80-100）
- 橙色 中高⻛险（60-79）
- ⻩色 中⻛险（40-59）
- 绿色 低⻛险（0-39）"""


class RiskAgent(BaseAgent):
    def __init__(self):
        tools = [calculate_risk_metrics, check_regulatory_events, read_announcement]
        config = AgentConfig(
            name="⻛控预警Agent", agent_type=AgentType.RISK,
            description="⻛险识别、量化评估、预警监控",
            system_prompt=RISK_AGENT_SYSTEM_PROMPT, tools=tools, max_iterations=6,
        )
        super().__init__(config)

    def _build_system_prompt(self) -> str:
        return self.config.system_prompt

    def _parse_output(self, raw_output: str) -> Dict[str, Any]:
        return {"analysis": raw_output, "agent_type": "risk"}

    async def assess_risk(self, stock_code: str, query: str = "") -> AgentExecutionResult:
        task = f"评估股票 {stock_code} ⻛险。计算⻛险指标，检查监管事件，识别财务⻛险，输出⻛险评分（0-100分）。{query}"
        return await self.execute(task=task)
