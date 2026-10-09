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
from langchain.schema import HumanMessage, AIMessage
from app.agents.report_agent import ReportAgent

from app.agents.base import AgentExecutionResult
from app.agents.researcher import ResearcherAgent
from app.agents.risk_agent import RiskAgent
from app.agents.strategist import StrategistAgent
from app.models.schemas import AgentType
from app.storage.conversations import get_conversation_store, ArchivedConversation
from app.config import get_settings

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
        "investment_advice": [AgentType.RESEARCHER, AgentType.RISK, AgentType.STRATEGIST],
        "risk_warning": [AgentType.RISK],
        "report": [AgentType.RESEARCHER, AgentType.RISK, AgentType.STRATEGIST, AgentType.REPORT],
        "general": [AgentType.RESEARCHER],
    }

    def __init__(self, config: Optional[OrchestratorConfig] = None):
        self.config = config or OrchestratorConfig()
        self._agents: Dict[AgentType, Any] = {}
        self.store = get_conversation_store()
        self._session_locks: Dict[str, asyncio.Lock] = {}
        self._capacity = asyncio.Semaphore(max(1, self.config.max_parallel_agents))
        self._init_agents()

    def _init_agents(self):
        self._agents = {
            AgentType.RESEARCHER: ResearcherAgent(),
            AgentType.RISK: RiskAgent(),
            AgentType.STRATEGIST: StrategistAgent(),
            AgentType.REPORT: ReportAgent(),
        }
        logger.info(f"[Orchestrator] initialized with {len(self._agents)} agents")

    def _classify_intent(self, query: str) -> str:
        q = query.lower().replace("⻛", "风")
        if any(k in q for k in ["报告", "研报"]):
            return "report"
        if any(k in q for k in ["风险", "风险评估", "暴雷", "违约", "亏损", "预警"]):
            if any(k in q for k in ["全面分析", "深度分析", "完整分析", "投资建议"]):
                return "full_analysis"
            return "stock_risk"
        if any(k in q for k in ["策略", "组合", "配置", "仓位", "建仓", "买入"]):
            return "investment_advice"
        if any(k in q for k in ["全面分析", "深度分析", "完整分析", "综合分析"]):
            return "full_analysis"
        if any(k in q for k in ["报告", "研报", "分析报告"]):
            return "report"
        if any(k in q for k in ["分析", "估值", "财务", "营收", "利润", "roe", "pe"]):
            return "stock_analysis"
        return "general"

    def _extract_stock_codes(self, query: str) -> List[str]:
        return re.findall(r'(?<![0-9])[0-9]{6}(?![0-9])', query)

    def _build_context(
        self, session_id: str, agent_results: Dict[AgentType, AgentExecutionResult]
    ) -> Dict[str, Any]:
        context = {"agent_results": {}, "session_id": session_id,
                   "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")}
        for agent_type, result in agent_results.items():
            if result.success:
                context["agent_results"][agent_type.value] = result.output
        return context

    def session_lock(self, session_id):
        return self._session_locks.setdefault(session_id, asyncio.Lock())

    async def run(self, query: str, session_id: Optional[str] = None,
                  agent_types: Optional[List[AgentType]] = None, parallel: bool = True,
                  context: Optional[Dict[str, Any]] = None, report_id: Optional[str] = None) -> Dict[str, Any]:
        session_id = session_id or str(uuid.uuid4())
        async with self.session_lock(session_id):
            session = await asyncio.to_thread(self.store.create, session_id)
            if session["archived"]:
                raise ArchivedConversation("请先恢复归档对话，再继续提问")
            run_id = str(uuid.uuid4())
            selected = list(dict.fromkeys(agent_types or self.INTENT_AGENT_MAP[self._classify_intent(query)]))
            if AgentType.REPORT in selected:
                selected = list(AgentType)
                if report_id is None:
                    codes = self._extract_stock_codes(query)
                    report = await asyncio.to_thread(self.store.create_report, query[:80],
                        codes[0] if codes else '', query, session_id, get_settings().LLM_MODEL)
                    report_id = report['id']
            elif AgentType.STRATEGIST in selected:
                selected = [AgentType.RESEARCHER, AgentType.RISK, AgentType.STRATEGIST]
            try:
                await asyncio.to_thread(self.store.start_run, run_id, session_id, query, report_id)
                return await self._run(query, session_id, selected, parallel, context, run_id, report_id)
            except BaseException as exc:
                error = '任务已取消或服务关闭' if isinstance(exc, asyncio.CancelledError) else str(exc)
                await asyncio.to_thread(self.store.fail_run, run_id, error, report_id)
                raise

    async def _run(
        self, query: str,
        session_id: Optional[str] = None,
        agent_types: Optional[List[AgentType]] = None,
        parallel: bool = True,
        context: Optional[Dict[str, Any]] = None,
        run_id: Optional[str] = None, report_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        session_id = session_id or str(uuid.uuid4())
        run_id = run_id or str(uuid.uuid4())

        logger.info(f"[Orchestrator] run_id={run_id} parallel={parallel}")

        # Step 1: intent classification
        intent = self._classify_intent(query)
        stock_codes = self._extract_stock_codes(query)

        # Step 2: select agents
        if agent_types:
            selected_agents = agent_types
        else:
            selected_agents = [AgentType(a) for a in self.INTENT_AGENT_MAP.get(intent, ["researcher"])]

        history = []
        budget = 20000
        turns = []
        for turn in reversed(await asyncio.to_thread(self.store.turns, session_id, 10)):
            size = len(turn["query"]) + len(turn["final_response"])
            if size > budget:
                break
            turns.insert(0, turn)
            budget -= size
        for turn in turns:
            history.extend([HumanMessage(content=turn["query"]),
                            AIMessage(content=turn["final_response"])])

        # Step 3: execute
        agent_results: Dict[AgentType, AgentExecutionResult] = {}

        async def execute_role(role):
            dependencies = []
            if role == AgentType.STRATEGIST:
                dependencies = [AgentType.RESEARCHER, AgentType.RISK]
            elif role == AgentType.REPORT:
                dependencies = [AgentType.RESEARCHER, AgentType.RISK, AgentType.STRATEGIST]
            if any(not agent_results.get(dep) or not agent_results[dep].success for dep in dependencies):
                return AgentExecutionResult(success=False, output='', error='上游分析失败，已跳过')
            shared = {**(context or {}), **self._build_context(session_id, agent_results)}
            # Full outputs are passed to dependent roles, not truncated to 200 characters.
            for dep in dependencies:
                shared[f'{dep.value}_result'] = agent_results[dep].output
            agent = self._agents.get(role)
            if agent is None:
                return AgentExecutionResult(success=False, output='', error='Agent 未注册')
            async with self._capacity:
                return await self._run_single_agent(agent, query, stock_codes, shared, history)

        roots = [role for role in selected_agents if role in (AgentType.RESEARCHER, AgentType.RISK)]
        if parallel:
            results = await asyncio.gather(*(execute_role(role) for role in roots))
            agent_results.update(zip(roots, results))
        else:
            for role in roots:
                agent_results[role] = await execute_role(role)
        for role in (AgentType.STRATEGIST, AgentType.REPORT):
            if role in selected_agents:
                agent_results[role] = await execute_role(role)

        # Step 4: aggregate
        final_response = self._aggregate_results(query, agent_results)

        # Only successful answers become conversational history.
        success = bool(agent_results) and all(r.success for r in agent_results.values())
        if success and report_id and (context or {}).get('rag_context'):
            # Keep downloaded reports self-contained with the exact evidence used by every role.
            appendix = ['\n\n---\n\n## 本轮知识库来源证据\n']
            for source in context['rag_context']:
                appendix.append(source.get('label', source['citation']))
                appendix.append(source['content'])
            final_response += '\n\n'.join(appendix)
        turn = None
        if success:
            turn = {
                "run_id": run_id, "query": query, "intent": intent,
                "agents_used": [a.value for a in selected_agents],
                "results": {k.value: v.output for k, v in agent_results.items()},
                "final_response": final_response,
                "response_metadata": {
                    "report_id": report_id,
                    "agent_type": selected_agents[-1].value,
                    "model": get_settings().LLM_MODEL,
                    "sources": (context or {}).get("rag_context", []),
                    "tool_calls": [dict(call, agent_type=k.value) for k, r in agent_results.items() for call in r.tool_calls],
                    "token_usage": {"total": sum(r.total_tokens for r in agent_results.values())},
                    "latency_ms": sum(r.execution_time_ms for r in agent_results.values()),
                },
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            }

        total_time = sum(r.execution_time_ms for r in agent_results.values())
        total_tokens = sum(r.total_tokens for r in agent_results.values())

        result = {
            "report_id": report_id,
            "run_id": run_id, "session_id": session_id, "intent": intent,
            "agent_results": {k.value: v.output for k, v in agent_results.items()},
            "agent_statuses": {k.value: {"success": v.success, "error": v.error} for k, v in agent_results.items()},
            "final_response": final_response, "success": success,
            "tool_calls": [dict(call, agent_type=k.value) for k, r in agent_results.items() for call in r.tool_calls],
            "execution_summary": {
                "agents_used": [a.value for a in selected_agents],
                "parallel": parallel, "total_execution_ms": total_time,
                "total_tokens": total_tokens,
                "success_count": sum(1 for r in agent_results.values() if r.success),
            },
        }

        await asyncio.to_thread(self.store.finish_run, run_id, result, turn, report_id)
        return result

    async def _run_single_agent(
        self, agent: Any, query: str, stock_codes: List[str],
        context: Optional[Dict[str, Any]] = None,
        history: Optional[List] = None,
    ) -> AgentExecutionResult:
        task = query
        if stock_codes:
            task = f"分析股票：{', '.join(stock_codes)}\n\n用戶问题：{query}"
        try:
            return await asyncio.wait_for(
                agent.execute(task=task, context=context, history=history),
                timeout=self.config.timeout_per_agent
            )
        except asyncio.TimeoutError:
            return AgentExecutionResult(
                success=False, output="", error=f"timeout > {self.config.timeout_per_agent}s"
            )
        except Exception as exc:
            return AgentExecutionResult(success=False, output='', error=str(exc))

    def _aggregate_results(
        self, query: str, agent_results: Dict[AgentType, AgentExecutionResult]
    ) -> str:
        for role in (AgentType.REPORT, AgentType.STRATEGIST):
            result = agent_results.get(role)
            if result and result.success and all(r.success for r in agent_results.values()):
                return result.output
        parts = []
        for agent_type in [AgentType.RESEARCHER, AgentType.RISK, AgentType.STRATEGIST, AgentType.REPORT]:
            result = agent_results.get(agent_type)
            if result and result.success and result.output:
                parts.append(f"\n## {agent_type.value.upper()} Result\n\n{result.output}\n")
        if not parts:
            errors = [f"{k.value}: {v.error}" for k, v in agent_results.items() if not v.success]
            return f"分析遇到问题：{'; '.join(errors)}"
        parts.extend(f"\n{key.value} 执行失败：{value.error}" for key, value in agent_results.items() if not value.success)
        return "\n".join(parts)

    def get_session_memory(self, session_id: str) -> List[Dict]:
        return self.store.turns(session_id, limit=10)

    def clear_session(self, session_id: str):
        self.store.clear(session_id)


_orchestrator: Optional[AgentOrchestrator] = None


def get_orchestrator() -> AgentOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AgentOrchestrator()
    return _orchestrator
