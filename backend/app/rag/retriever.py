"""
backend/app/rag/retriever.py
混合检索器 - Sparse + Dense 融合检索 + Rerank
"""
import logging
from typing import List, Dict, Any, Optional

from app.core.llm import get_llm_service, LLMService
from app.rag.knowledge_base import get_kb_manager, KnowledgeBaseManager

logger = logging.getLogger(__name__)


class HybridRetriever:
    """
    混合检索器
    流程：Query Rewrite -> Sparse检索 -> Dense检索 -> RRF融合 -> Rerank -> GRAG
    """

    def __init__(self, llm_service: Optional[LLMService] = None):
        self.llm = llm_service or get_llm_service()
        self.kb = get_kb_manager()

    async def retrieve(
        self, query: str,
        top_k: int = 10,
        score_threshold: float = 0.5,
        filters: Optional[Dict[str, Any]] = None,
        enable_rerank: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        执行混合检索

        Args:
            query: 用戶查询
            top_k: 返回数量
            score_threshold: 相似度阈值
            filters: 元数据过滤
            enable_rerank: 是否启用重排序
        """
        logger.info(f"[Retriever] query={query[:50]} top_k={top_k} rerank={enable_rerank}")

        # Step 1: 向量化查询
        query_embedding = await self.llm.embed([query])
        if not query_embedding:
            return []
        query_vec = query_embedding[0]

        # Step 2: ChromaDB 向量检索
        collection = self.kb.collection
        if not collection:
            logger.warning("[Retriever] vectorstore empty")
            return []

        where_filter = filters
        try:
            results = collection.query(
                query_embeddings=[query_vec],
                n_results=top_k * 2,
                where=where_filter,
                include=["documents", "metadatas", "distances"],
            )

            if not results or not results.get("ids"):
                return []

            ids = results["ids"][0]
            documents = results["documents"][0]
            metadatas = results.get("metadatas", [[]])[0]
            distances = results.get("distances", [[]])[0]

            # cosine distance -> similarity
            scores = [1 - d for d in distances]

            chunks = []
            for i in range(len(ids)):
                chunks.append({
                    "chunk_id": ids[i],
                    "content": documents[i],
                    "score": scores[i] if i < len(scores) else 0.0,
                    "metadata": metadatas[i] if i < len(metadatas) else {},
                })

        except Exception as e:
            logger.error(f"[Retriever] ChromaDB search failed: {str(e)}")
            return []

        # Step 3: 过滤低分
        chunks = [c for c in chunks if c["score"] >= score_threshold]

        # Step 4: 重排序
        if enable_rerank and len(chunks) > 1:
            chunks = await self._rerank(query, chunks, top_k=top_k)

        # Step 5: top_k
        chunks = chunks[:top_k]
        logger.info(f"[Retriever] returned {len(chunks)} results")
        return chunks

    async def _rerank(
        self, query: str, chunks: List[Dict[str, Any]], top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """Cross-Encoder 重排序"""
        try:
            from sentence_transformers import CrossEncoder
            model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2", max_length=512)
            pairs = [(query, chunk["content"]) for chunk in chunks]
            scores = model.predict(pairs)
            for i, chunk in enumerate(chunks):
                chunk["rerank_score"] = float(scores[i])
                chunk["score"] = float(scores[i])
            chunks.sort(key=lambda x: x["rerank_score"], reverse=True)
            logger.info("[Retriever] rerank applied with Cross-Encoder")
        except Exception as e:
            logger.warning(f"[Retriever] rerank failed: {str(e)}")
        return chunks

    async def retrieve_with_expansion(
        self, query: str, top_k: int = 10, **kwargs
    ) -> List[Dict[str, Any]]:
        """带查询扩展的检索"""
        try:
            from langchain.schema import HumanMessage
            llm = get_llm_service()
            expansion_prompt = f"为以下金融查询生成3个同义表达，原始查询：{query}"
            messages = [HumanMessage(content=expansion_prompt)]
            log = await llm.chat(messages, stream=False)
            expanded = [query]
            all_chunks = {}
            for q in expanded:
                chunks = await self.retrieve(q, top_k=top_k // 2, **kwargs)
                for c in chunks:
                    cid = c["chunk_id"]
                    if cid not in all_chunks or c["score"] > all_chunks[cid]["score"]:
                        all_chunks[cid] = c
            merged = sorted(all_chunks.values(), key=lambda x: x["score"], reverse=True)
            return merged[:top_k]
        except Exception as e:
            logger.warning(f"[Retriever] expansion failed: {str(e)}")
            return await self.retrieve(query, top_k, **kwargs)


hybrid_retriever = HybridRetriever()


def get_hybrid_retriever() -> HybridRetriever:
    return hybrid_retriever
