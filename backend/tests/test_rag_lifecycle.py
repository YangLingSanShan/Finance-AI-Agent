from types import SimpleNamespace
from unittest.mock import AsyncMock
import chromadb
import pytest
from langchain.schema import Document
from app.rag import documents
from app.rag.knowledge_base import KnowledgeBaseManager
from app.rag.retriever import HybridRetriever, evidence_context
from app.rag.query_rewrite import QueryRewriter


@pytest.fixture
def corpus(tmp_path, monkeypatch):
    llm = AsyncMock()
    llm.embed.side_effect = lambda texts: [[1., 0., 0.] for _ in texts]
    llm.chat.return_value = SimpleNamespace(success=True, content='{"rewritten_query":"营业收入"}')
    kb = KnowledgeBaseManager(llm)
    kb._collection = chromadb.PersistentClient(path=str(tmp_path / 'vectors')).create_collection('rag_test', metadata={'hnsw:space': 'cosine'})
    monkeypatch.setattr(documents, 'get_kb_manager', lambda: kb)
    retriever = HybridRetriever(llm)
    retriever.kb = kb
    return kb, retriever


async def test_lifecycle_dedup_update_delete_and_filters(corpus):
    kb, retriever = corpus
    pages = [Document(page_content='营业收入为100亿元，2025年度，单位亿元。', metadata={'page': 3})]
    meta = {'stock_code': '600519', 'disclosure_date': '2026-03-01', 'source_url': 'https://example.org/report'}
    first = await documents.ingest('年报', 'annual', pages, meta)
    again = await documents.ingest('年报', 'annual', pages, meta)
    assert again['id'] == first['id'] and again['deduplicated']
    assert kb.collection.count() == 1
    assert not await retriever.retrieve('营业收入', filters={'stock_code': '300750'})
    assert not await retriever.retrieve('营业收入', filters={'disclosure_date': {'$lte': '2025-12-31'}})
    found = await retriever.retrieve('营业收入', filters={'stock_code': '600519', 'disclosure_date': {'$gte': '2026-01-01'}})
    assert found[0]['metadata']['page'] == 3
    evidence = evidence_context(found)
    assert evidence[0]['citation'] == '来源1' and '页码:3' in evidence[0]['label']
    await documents.ingest('年报', 'annual', [Document(page_content='营业收入更正为200亿元', metadata={'page': 4})], meta, first['id'])
    found = await retriever.retrieve('营业收入')
    assert len(found) == 1 and '200亿元' in found[0]['content']
    await documents.remove(first['id'])
    assert not await retriever.retrieve('营业收入')
    assert kb.collection.count() == 0


async def test_failed_update_keeps_published_revision(corpus):
    kb, retriever = corpus
    item = await documents.ingest('公告', 'general', [Document(page_content='原始披露')])
    kb.llm.embed.side_effect = RuntimeError('offline')
    with pytest.raises(RuntimeError):
        await documents.ingest('公告', 'general', [Document(page_content='失败的更新')], doc_id=item['id'])
    assert documents.store().get_document(item['id'])['payload']['revision'] == item['payload']['revision']
    assert kb.collection.count() == 1


async def test_reindex_and_rewrite(corpus):
    kb, _ = corpus
    item = await documents.ingest('公告', 'general', [Document(page_content='利润增长')])
    updated = await documents.ingest('公告', 'general', [Document(page_content='利润增长')], doc_id=item['id'], force=True)
    assert updated['payload']['revision'] != item['payload']['revision']
    assert kb.collection.count() == 1
    rewriter = QueryRewriter(); rewriter.llm = kb.llm
    assert (await rewriter.rewrite('收入'))['rewritten_query'] == '营业收入'


def test_upload_validation_and_sections():
    with pytest.raises(ValueError): documents.parse_file('x.exe', b'data')
    with pytest.raises(ValueError): documents.parse_file('x.txt', b'')
    with pytest.raises(ValueError): documents.parse_file('x.txt', b'x' * (documents.MAX_BYTES + 1))
    pages = documents.parse_file('x.md', '# 财务\n2025 年 单位：亿元\n收入 100'.encode())
    assert pages[0].metadata['section'] == '财务'
    assert '单位' in pages[0].page_content
    with pytest.raises(ValueError): documents.validate_metadata({'source_url': 'javascript:alert(1)'})


def test_evidence_budget_does_not_truncate_to_200():
    result = evidence_context([{'content': '营' * 500, 'metadata': {'page': 2}}], budget=800)
    assert len(result[0]['content']) == 500
    result = evidence_context([{'content': '营' * 1000, 'metadata': {}}], budget=300)
    assert len(result[0]['content']) + len(result[0]['label']) <= 300


def test_upload_api_roundtrip(corpus):
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as client:
        url = '/api/v1/rag/knowledge'
        response = client.post(url + '/upload', files={'file': ('report.md', '# 年报\n收入100亿元'.encode())},
            data={'metadata': '{"stock_code":"600519"}'})
        assert response.status_code == 200
        doc_id = response.json()['id']
        assert client.get(url + '/stats').json()['total_documents'] == 1
        assert client.get(url + '/documents').json()[0]['id'] == doc_id
        assert client.get(url + '/documents/' + doc_id).json()['payload']['pages'][0]['metadata']['section'] == '年报'
        assert client.post(url + '/upload', files={'file': ('x.exe', b'bad')}).status_code == 400
        assert client.post('/api/v1/rag/query', json={'query': '收入', 'filters': {'stock_code': 123}}).status_code == 400
        assert client.delete(url + '/documents/' + doc_id).status_code == 200
        assert client.get(url + '/documents/' + doc_id).status_code == 404


async def test_rerank_failure_reports_fallback(corpus, monkeypatch):
    from app.rag import retriever as module
    kb, retriever = corpus
    await documents.ingest('甲', 'general', [Document(page_content='营业收入增长')])
    await documents.ingest('乙', 'general', [Document(page_content='营业收入下降')])
    monkeypatch.setattr(module, 'get_settings', lambda: SimpleNamespace(RAG_RERANK_MODEL='missing'))
    def unavailable(path): raise RuntimeError('missing weights')
    monkeypatch.setattr(module, 'reranker', unavailable)
    result = await retriever.retrieve('营业收入')
    assert len(result) == 2
    assert all(not c['rerank_applied'] and c['rerank_warning'] for c in result)


def test_embedding_profile_changes_with_model_or_dimension(corpus):
    kb, _ = corpus
    kb.settings = SimpleNamespace(EMBEDDING_API_BASE='https://example.org', EMBEDDING_MODEL='one', EMBEDDING_DIM=3)
    first = kb.index_profile
    kb.settings.EMBEDDING_DIM = 4
    assert kb.index_profile != first
    kb.settings.EMBEDDING_DIM = 3; kb.settings.EMBEDDING_MODEL = 'two'
    assert kb.index_profile != first
