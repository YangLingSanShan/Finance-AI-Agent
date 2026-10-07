"""
backend/app/agents/risk_agent.py
⻛控预警 Agent - ⻛险识别、量化评估、预警
"""
from typing import Dict, Any
from app.agents.base import BaseAgent, AgentConfig, AgentExecutionResult
from app.models.schemas import AgentType
from langchain.tools import tool


@tool(description="计算股票⻛险指标（波动率、VaR、Beta等）")
def calculate_risk_metrics(stock_code: str, period: int = 60) -> str:
    return '{"code": "stock_code", "volatility": 0.25, "var_95": -0.03, "beta": 1.2}'


@tool(description="检查监管处罚和诉讼信息")
def check_regulatory_events(stock_code: str) -> str:
    return '[{"event": "处罚/诉讼事件", "date": "日期", "severity": "严重程度"}]'


RISK_AGENT_SYSTEM_PROMPT = """当前金融工具返回的是演示数据，不是真实行情。使用工具结果时必须明确标记为演示，不能据此给出真实投资结论。
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
        tools = [calculate_risk_metrics, check_regulatory_events]
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
