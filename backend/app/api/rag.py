"""
backend/app/api/rag.py
RAG 知识库 API
"""
import logging
from fastapi import APIRouter, HTTPException
from app.models.schemas import RAGQueryRequest, RAGQueryResponse, KnowledgeBaseUpload
from app.rag.retriever import get_hybrid_retriever
from app.rag.knowledge_base import get_kb_manager

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/rag/query", response_model=RAGQueryResponse)
async def rag_query(request: RAGQueryRequest):
    """RAG 检索接口"""
    try:
        retriever = get_hybrid_retriever()
        chunks = await retriever.retrieve(
            query=request.query, top_k=request.top_k,
            score_threshold=request.score_threshold,
            filters=request.filters, enable_rerank=request.enable_rerank,
        )
        return RAGQueryResponse(
            query=request.query,
            chunks=[{"content": c["content"], "score": round(c["score"], 3),
                     "metadata": c.get("metadata", {})} for c in chunks],
            total_retrieved=len(chunks), rerank_applied=request.enable_rerank,
        )
    except Exception as e:
        logger.error(f"[RAG API] query failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rag/knowledge/add")
async def add_knowledge(request: KnowledgeBaseUpload):
    """添加知识库内容"""
    try:
        kb = get_kb_manager()
        count = await kb.add_text_chunks(
            texts=[request.content], category=request.category,
            metadata_list=[{"title": request.title, **(request.metadata or {})}],
        )
        return {"message": f"added {count} chunks", "title": request.title, "category": request.category}
    except Exception as e:
        logger.error(f"[RAG API] add failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rag/knowledge/stats")
async def get_knowledge_stats():
    kb = get_kb_manager()
    count = kb.count_documents()
    return {"total_chunks": count, "vectorstore_type": "chroma", "status": "healthy"}
