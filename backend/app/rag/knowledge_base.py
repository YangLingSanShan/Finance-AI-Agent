"""
backend/app/rag/knowledge_base.py
RAG 知识库管理 - 文档加载、分块、索引
"""
import uuid
import asyncio
import hashlib
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document

from app.core.llm import get_llm_service, LLMService
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class ChunkResult:
    chunk_id: str
    content: str
    metadata: Dict[str, Any]
    embedding: Optional[List[float]] = None


class KnowledgeBaseManager:
    """
    知识库管理器
    职责：文档加载 | 文档分块 | 向量化存储 | 知识检索
    """

    def __init__(self, llm_service: Optional[LLMService] = None):
        self.llm = llm_service or get_llm_service()
        self.settings = get_settings()
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500, chunk_overlap=50,
            length_function=len,
            separators=["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""],
        )
        self._collection = None

    @property
    def index_profile(self):
        identity = f'{self.settings.EMBEDDING_API_BASE}|{self.settings.EMBEDDING_MODEL}|{self.settings.EMBEDDING_DIM}'
        return hashlib.sha256(identity.encode()).hexdigest()[:16]

    @property
    def collection(self):
        if self._collection is None:
            try:
                import chromadb
                from chromadb.config import Settings as ChromaSettings
                client = chromadb.PersistentClient(
                    path=self.settings.CHROMA_PERSIST_DIR,
                    settings=ChromaSettings(anonymized_telemetry=False)
                )
                self._collection = client.get_or_create_collection(
                    name=f"{self.settings.CHROMA_COLLECTION_NAME}_{self.index_profile}",
                    metadata={"hnsw:space": "cosine"}
                )
                logger.info(f"[KB] ChromaDB initialized: {self.settings.CHROMA_COLLECTION_NAME}")
            except ImportError:
                logger.warning("[KB] ChromaDB not installed")
                self._collection = None
        return self._collection

    def chunk_documents(
        self, documents: List[Document],
        chunk_size: int = 500, chunk_overlap: int = 50,
    ) -> List[ChunkResult]:
        """文档分块"""
        splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", "。", "；", "，", " ", ""])
        chunks = splitter.split_documents(documents)
        results = []
        for i, chunk in enumerate(chunks):
            chunk_id = str(uuid.uuid4())
            results.append(ChunkResult(
                chunk_id=chunk_id,
                content=chunk.page_content,
                metadata={
                    **chunk.metadata,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "content_hash": hashlib.md5(chunk.page_content.encode()).hexdigest(),
                }
            ))
        logger.info(f"[KB] chunked: {len(documents)} docs -> {len(results)} chunks")
        return results

    async def add_chunks_to_vectorstore(
        self, chunks: List[ChunkResult], batch_size: int = 20,
    ) -> int:
        """将文档块添加到向量存储"""
        if not self.collection:
            logger.warning("[KB] vectorstore not initialized")
            return 0

        texts = [c.content for c in chunks]
        metadatas = [c.metadata for c in chunks]
        ids = [c.chunk_id for c in chunks]

        total_added = 0
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            batch_metas = metadatas[i:i + batch_size]
            batch_ids = ids[i:i + batch_size]
            embeddings = await self.llm.embed(batch_texts)
            if len(embeddings) != len(batch_texts):
                raise RuntimeError('Embedding 返回数量与文本数量不一致')
            await asyncio.to_thread(self.collection.upsert, embeddings=embeddings, documents=batch_texts,
                                    metadatas=batch_metas, ids=batch_ids)
            total_added += len(batch_texts)

        logger.info(f"[KB] added {total_added} chunks to vectorstore")
        return total_added

    async def add_text_chunks(
        self, texts: List[str], category: str = "general",
        metadata_list: Optional[List[Dict]] = None,
    ) -> int:
        """直接添加文本块"""
        results = []
        for i, text in enumerate(texts):
            meta = metadata_list[i] if metadata_list else {}
            results.append(ChunkResult(
                chunk_id=str(uuid.uuid4()), content=text,
                metadata={**meta, "category": category}
            ))
        return await self.add_chunks_to_vectorstore(results)

    def count_documents(self) -> int:
        if self.collection:
            return self.collection.count()
        return 0


kb_manager = KnowledgeBaseManager()


def get_kb_manager() -> KnowledgeBaseManager:
    return kb_manager
