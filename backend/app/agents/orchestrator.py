"""
backend/app/agents/orchestrator.py
Agent 编排器 - 多Agent协同调度核心
"""
import uuid
import time
import logging
import re
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import asyncio

from app.agents.base import AgentExecutionResult
from app.agents.researcher import ResearcherAgent
from app.agents.risk_agent import RiskAgent
from app.agents.strategist import StrategistAgent
from app.models.schemas import AgentType

logger = logging.getLogger(__name__)


@dataclass
class OrchestratorConfig:
    max_parallel_agents: int = 3
    timeout_per_agent: int = 60
    enable_caching: bool = True


class AgentOrchestrator:
    """
    多Agent编排器
    核心能力：意图分类 | 任务拆解 | 并行/串行执行 | 结果聚合 | 记忆管理
    """

    INTENT_AGENT_MAP = {
        "stock_analysis": [AgentType.RESEARCHER],
        "stock_risk": [AgentType.RISK],
        "full_analysis": [AgentType.RESEARCHER, AgentType.RISK, AgentType.STRATEGIST],
        "investment_advice": [AgentType.RESEARCHER, AgentType.STRATEGIST],
        "risk_warning": [AgentType.RISK],
        "report": [AgentType.RESEARCHER],
        "general": [AgentType.RESEARCHER],
    }

    def __init__(self, config: Optional[OrchestratorConfig] = None):
        self.config = config or OrchestratorConfig()
        self._agents: Dict[AgentType, Any] = {}
        self._session_memory: Dict[str, List[Dict]] = {}
        self._init_agents()

    def _init_agents(self):
        self._agents = {
            AgentType.RESEARCHER: ResearcherAgent(),
            AgentType.RISK: RiskAgent(),
            AgentType.STRATEGIST: StrategistAgent(),
        }
        logger.info(f"[Orchestrator] initialized with {len(self._agents)} agents")

    def _classify_intent(self, query: str) -> str:
        q = query.lower()
        if any(k in q for k in ["⻛险", "⻛险评估", "暴雷", "违约", "亏损", "预警"]):
            if any(k in q for k in ["全面分析", "深度分析", "完整分析", "投资建议"]):
                return "full_analysis"
            return "stock_risk"
        if any(k in q for k in ["策略", "组合", "配置", "仓位", "建仓", "买入"]):
            return "investment_advice"
        if any(k in q for k in ["全面分析", "深度分析", "完整分析", "综合分析"]):
            return "full_analysis"
        if any(k in q for k in ["报告", "研报", "分析报告"]):
            return "report"
        if any(k in q for k in ["分析", "估值", "财务", "营收", "利润", "ROE", "PE"]):
            return "stock_analysis"
        return "general"

    def _extract_stock_codes(self, query: str) -> List[str]:
        return re.findall(r'\b\d{6}\b', query)

    def _build_context(
        self, session_id: str, agent_results: Dict[AgentType, AgentExecutionResult]
    ) -> Dict[str, Any]:
        context = {"agent_results": {}, "session_id": session_id,
                   "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")}
        for agent_type, result in agent_results.items():
            if result.success:
                context["agent_results"][agent_type.value] = result.output
        return context

    async def run(
        self, query: str,
        session_id: Optional[str] = None,
        agent_types: Optional[List[AgentType]] = None,
        parallel: bool = True,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        session_id = session_id or str(uuid.uuid4())
        run_id = str(uuid.uuid4())

        logger.info(f"[Orchestrator] run_id={run_id} parallel={parallel}")

        # Step 1: intent classification
        intent = self._classify_intent(query)
        stock_codes = self._extract_stock_codes(query)

        # Step 2: select agents
        if agent_types:
            selected_agents = agent_types
        else:
            selected_agents = [AgentType(a) for a in self.INTENT_AGENT_MAP.get(intent, ["researcher"])]

        # Step 3: execute
        agent_results: Dict[AgentType, AgentExecutionResult] = {}

        if parallel and len(selected_agents) > 1:
            tasks = []
            for agent_type in selected_agents:
                agent = self._agents.get(agent_type)
                if agent:
                    tasks.append((agent_type, self._run_single_agent(agent, query, stock_codes, context)))

            results = await asyncio.gather(*[t for _, t in tasks], return_exceptions=True)
            for i, (agent_type, _) in enumerate(tasks):
                result = results[i]
                if isinstance(result, Exception):
                    agent_results[agent_type] = AgentExecutionResult(success=False, output="", error=str(result))
                else:
                    agent_results[agent_type] = result
        else:
            shared_context = context or {}
            for agent_type in selected_agents:
                agent = self._agents.get(agent_type)
                if agent:
                    if agent_type == AgentType.RISK and agent_results.get(AgentType.RESEARCHER):
                        shared_context["researcher_result"] = agent_results[AgentType.RESEARCHER].output
                    result = await self._run_single_agent(agent, query, stock_codes, shared_context)
                    agent_results[agent_type] = result

        # Step 4: aggregate
        final_response = self._aggregate_results(query, agent_results)

        # Step 5: record session
        self._session_memory.setdefault(session_id, []).append({
            "run_id": run_id, "query": query, "intent": intent,
            "agents_used": [a.value for a in selected_agents],
            "results": {k.value: v.output for k, v in agent_results.items()},
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        })

        total_time = sum(r.execution_time_ms for r in agent_results.values())
        total_tokens = sum(r.total_tokens for r in agent_results.values())

        return {
            "run_id": run_id, "session_id": session_id, "intent": intent,
            "agent_results": {k.value: v.output for k, v in agent_results.items()},
            "final_response": final_response,
            "execution_summary": {
                "agents_used": [a.value for a in selected_agents],
                "parallel": parallel, "total_execution_ms": total_time,
                "total_tokens": total_tokens,
                "success_count": sum(1 for r in agent_results.values() if r.success),
            },
        }

    async def _run_single_agent(
        self, agent: Any, query: str, stock_codes: List[str],
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentExecutionResult:
        task = query
        if stock_codes:
            task = f"分析股票：{', '.join(stock_codes)}\n\n用戶问题：{query}"
        try:
            return await asyncio.wait_for(
                agent.execute(task=task, context=context),
                timeout=self.config.timeout_per_agent
            )
        except asyncio.TimeoutError:
            return AgentExecutionResult(
                success=False, output="", error=f"timeout > {self.config.timeout_per_agent}s"
            )

    def _aggregate_results(
        self, query: str, agent_results: Dict[AgentType, AgentExecutionResult]
    ) -> str:
        parts = []
        for agent_type in [AgentType.RESEARCHER, AgentType.RISK, AgentType.STRATEGIST]:
            result = agent_results.get(agent_type)
            if result and result.success and result.output:
                parts.append(f"\n## {agent_type.value.upper()} Result\n\n{result.output}\n")
        if not parts:
            errors = [f"{k.value}: {v.error}" for k, v in agent_results.items() if not v.success]
            return f"分析遇到问题：{'; '.join(errors)}"
        return "\n".join(parts)

    def get_session_memory(self, session_id: str) -> List[Dict]:
        return self._session_memory.get(session_id, [])

    def clear_session(self, session_id: str):
        if session_id in self._session_memory:
            del self._session_memory[session_id]


_orchestrator: Optional[AgentOrchestrator] = None


def get_orchestrator() -> AgentOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AgentOrchestrator()
    return _orchestrator
