"""
backend/app/api/chat.py
对话聊天 API
"""
import uuid
import time
import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from app.models.schemas import ChatRequest, ChatResponse, AgentType
from app.agents.orchestrator import get_orchestrator
from app.llmops.monitor import get_llmops_monitor
from app.rag.retriever import get_hybrid_retriever

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    对话接口
    流程：接收消息 -> RAG检索 -> Agent执行 -> 返回结果
    """
    session_id = request.session_id or str(uuid.uuid4())
    start_time = time.time()
    context = {}

    try:
        # RAG 检索
        sources = []
        if request.enable_rag:
            retriever = get_hybrid_retriever()
            chunks = await retriever.retrieve(query=request.message, top_k=5, enable_rerank=True)
            if chunks:
                context["rag_context"] = chunks
                sources = [{"content": c["content"][:200] + "...", "score": round(c["score"], 3),
                            "metadata": c.get("metadata", {})} for c in chunks]

        # Agent 执行
        orchestrator = get_orchestrator()
        agent_types = [request.agent_type] if request.agent_type else None
        result = await orchestrator.run(
            query=request.message, session_id=session_id,
            agent_types=agent_types, parallel=False, context=context,
        )

        latency = (time.time() - start_time) * 1000

        # 记录 LLMOps
        monitor = get_llmops_monitor()
        monitor.log_call(
            model="orchestrator", prompt_tokens=0,
            completion_tokens=len(result["final_response"]) // 4,
            total_tokens=result["execution_summary"]["total_tokens"],
            latency_ms=latency, cost_usd=0.0, success=True,
            session_id=session_id, prompt_preview=request.message[:100],
        )

        return ChatResponse(
            session_id=session_id, message=result["final_response"],
            agent_type=AgentType.RESEARCHER,
            sources=sources if sources else None,
            token_usage={"total": result["execution_summary"]["total_tokens"]},
            latency_ms=round(latency, 2),
        )

    except Exception as e:
        logger.error(f"[Chat] failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """流式对话接口（SSE）"""
    session_id = request.session_id or str(uuid.uuid4())

    async def generate():
        try:
            orchestrator = get_orchestrator()
            result = await orchestrator.run(query=request.message, session_id=session_id)
            response_text = result["final_response"]
            for i in range(0, len(response_text), 50):
                chunk = response_text[i:i + 50]
                yield f"event: message\ndata: {chunk}\n\n"
            yield f"event: done\ndata: done\n\n"
        except Exception as e:
            yield f"event: error\ndata: {str(e)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
