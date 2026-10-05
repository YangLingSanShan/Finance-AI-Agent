"""
backend/app/agents/strategist.py
策略生成 Agent - 投资策略、组合建议、交易方案
"""
from typing import Dict, Any
from app.agents.base import BaseAgent, AgentConfig, AgentExecutionResult
from app.models.schemas import AgentType


STRATEGIST_SYSTEM_PROMPT = """你是资深量化投资策略师，精通多因子模型、资产配置。

策略原则：
- ⻛险收益匹配：诚实告知用戶
- 分散化：单一标的仓位不超过20%
- 流动性优先：日均成交额>1亿
- 动态调整：根据市场环境调整

输出框架：
1. 策略概述：类型、适用场景、预期收益与⻛险
2. 选股标准：行业、市值、估值筛选条件
3. 仓位配置：各标的仓位、入场点位、止损线
4. ⻛险控制：最大回撤控制、动态止损规则

重要声明：仅供参考，不构成投资建议"""


class StrategistAgent(BaseAgent):
    def __init__(self):
        config = AgentConfig(
            name="策略生成Agent", agent_type=AgentType.STRATEGIST,
            description="投资策略、组合建议、交易方案",
            system_prompt=STRATEGIST_SYSTEM_PROMPT, tools=[], max_iterations=5,
        )
        super().__init__(config)

    def _build_system_prompt(self) -> str:
        return self.config.system_prompt

    def _parse_output(self, raw_output: str) -> Dict[str, Any]:
        return {"strategy": raw_output, "agent_type": "strategist"}

    async def generate_strategy(self, context: Dict[str, Any]) -> AgentExecutionResult:
        task = f"""基于以下分析结果生成投资策略：

研究结论：{context.get('researcher_result', '无')}
⻛控结论：{context.get('risk_result', '无')}
用戶偏好：{context.get('user_preference', '无')}

请按策略框架输出。"""
        return await self.execute(task=task, context=context)
