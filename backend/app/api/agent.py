"""
backend/app/api/agent.py
Agent 编排 API
"""
import uuid
import asyncio
import logging
from app.storage.conversations import ArchivedConversation
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from app.models.schemas import AgentInvokeRequest, AgentType
from app.agents.orchestrator import get_orchestrator

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/agent/invoke")
async def invoke_agent(request: AgentInvokeRequest):
    """直接调用 Agent 编排器"""
    try:
        orchestrator = get_orchestrator()
        result = await orchestrator.run(
            query=request.query,
            session_id=request.session_id or str(uuid.uuid4()),
            agent_types=request.agent_types,
            parallel=request.parallel,
        )
        if not result["success"]:
            raise HTTPException(status_code=502, detail=result["final_response"])
        return {
            "tool_calls": result["tool_calls"], "report_id": result.get("report_id"),
            "agent_statuses": result.get("agent_statuses", {}),
            "run_id": result["run_id"], "session_id": result["session_id"],
            "intent": result["intent"], "final_response": result["final_response"],
            "execution_summary": result["execution_summary"],
        }
    except ArchivedConversation as e:
        raise HTTPException(status_code=409, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Agent API] failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agent/memory/{session_id}")
def get_session_memory(session_id: str):
    orchestrator = get_orchestrator()
    memory = orchestrator.get_session_memory(session_id)
    return {"session_id": session_id, "conversation_turns": len(memory), "memory": memory}


@router.delete("/agent/memory/{session_id}")
async def clear_session_memory(session_id: str):
    orchestrator = get_orchestrator()
    async with orchestrator.session_lock(session_id):
        await asyncio.to_thread(orchestrator.clear_session, session_id)
    return {"message": "session cleared", "session_id": session_id}


@router.get("/agent/types")
async def list_agent_types():
    return {
        "agents": [
            {"type": "report", "name": "报告生成Agent", "description": "综合分析生成报告", "capabilities": ["report"]},
            {"type": "researcher", "name": "投研分析Agent",
             "description": "股票基本面分析", "capabilities": ["stock_analysis", "financial_report"]},
            {"type": "risk", "name": "⻛控预警Agent",
             "description": "⻛险识别评估", "capabilities": ["risk_assessment", "risk_warning"]},
            {"type": "strategist", "name": "策略生成Agent",
             "description": "投资策略建议", "capabilities": ["strategy_generation", "portfolio"]},
        ]
    }


@router.get("/agent/runs/{run_id}")
def get_run(run_id: str):
    try:
        return get_orchestrator().store.get_run(run_id)
    except KeyError:
        raise HTTPException(404, '运行记录不存在')
