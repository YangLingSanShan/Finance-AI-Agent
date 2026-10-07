from unittest.mock import AsyncMock

import chromadb
from chromadb.config import Settings
from langchain.schema import Document

from app.rag.knowledge_base import KnowledgeBaseManager
from app.rag.retriever import HybridRetriever


async def test_local_vectorstore_roundtrip_and_metadata_filter(tmp_path):
    llm = AsyncMock()
    llm.embed.return_value = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
    kb = KnowledgeBaseManager(llm_service=llm)
    client = chromadb.PersistentClient(
        path=str(tmp_path / 'chroma'), settings=Settings(anonymized_telemetry=False),
    )
    kb._collection = client.create_collection('test_financial', metadata={'hnsw:space': 'cosine'})
    count = await kb.add_text_chunks(
        ['公司A营收增长', '公司B利润下降'], category='annual_report',
        metadata_list=[{'stock_code': '600519', 'page': 3}, {'stock_code': '300750', 'page': 5}],
    )
    assert count == 2
    assert kb.count_documents() == 2
    llm.embed.return_value = [[1.0, 0.0, 0.0]]
    retriever = HybridRetriever(llm_service=llm)
    retriever.kb = kb
    results = await retriever.retrieve(
        '公司A营收', top_k=1, filters={'stock_code': '600519'}, enable_rerank=False,
    )
    assert len(results) == 1
    assert results[0]['content'] == '公司A营收增长'
    assert results[0]['metadata']['page'] == 3
    assert results[0]['score'] > 0.99


def test_document_chunking_preserves_provenance():
    kb = KnowledgeBaseManager(llm_service=AsyncMock())
    chunks = kb.chunk_documents([Document(
        page_content='营收增长。' * 200, metadata={'stock_code': '600519', 'page': 3},
    )])
    assert len(chunks) > 1
    assert all(len(chunk.content) <= 500 for chunk in chunks)
    assert all(chunk.metadata['page'] == 3 for chunk in chunks)
    assert len({chunk.chunk_id for chunk in chunks}) == len(chunks)
