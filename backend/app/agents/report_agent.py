"""
backend/app/agents/report_agent.py
报告生成 Agent - 自动生成结构化投研报告
"""
from typing import Dict, Any
from app.agents.base import BaseAgent, AgentConfig, AgentExecutionResult
from app.models.schemas import AgentType


REPORT_SYSTEM_PROMPT = """你是专业金融研究报告撰写专家。

报告框架：
1. 执行摘要（100字内）
2. 公司概况：主营业务、市场地位
3. 基本面分析：营收、利润、现金流趋势
4. 估值分析：PE/PB/PS 对比
5. ⻛险因素
6. 投资建议（买入/持有/卖出）

格式：Markdown，数据表格，结论加粗"""


class ReportAgent(BaseAgent):
    def __init__(self):
        config = AgentConfig(
            name="报告生成Agent", agent_type=AgentType.REPORT,
            description="自动生成结构化投研报告",
            system_prompt=REPORT_SYSTEM_PROMPT, tools=[], max_iterations=3,
        )
        super().__init__(config)

    def _build_system_prompt(self) -> str:
        return self.config.system_prompt

    def _parse_output(self, raw_output: str) -> Dict[str, Any]:
        return {"report": raw_output, "agent_type": "report"}

    async def generate_report(self, stock_code: str, analysis_data: Dict[str, Any]) -> AgentExecutionResult:
        task = f"为股票 {stock_code} 生成完整投研报告。数据：{analysis_data}"
        return await self.execute(task=task)
