from unittest.mock import AsyncMock
from fastapi.testclient import TestClient
from app.main import app
from app.agents.orchestrator import get_orchestrator
from app.agents.base import AgentExecutionResult
from app.api import chat, reports
from app.rag import retriever


def test_chat_retrieval_failure_is_not_empty_evidence(monkeypatch):
    search = AsyncMock()
    search.retrieve.side_effect = RuntimeError('sensitive provider detail')
    monkeypatch.setattr(chat, 'get_hybrid_retriever', lambda: search)
    o = get_orchestrator()
    o.run = AsyncMock()
    with TestClient(app) as client:
        response = client.post('/api/v1/chat', json={'session_id': '', 'message': '600519分红', 'enable_rag': True})
        assert response.status_code == 503
        assert '检索服务暂不可用' in response.json()['detail']
        assert 'sensitive' not in response.text
    o.run.assert_not_called()
    assert search.retrieve.call_args.kwargs['filters'] == {'stock_code': '600519'}


def test_empty_evidence_and_citations_survive_history(monkeypatch):
    search = AsyncMock()
    monkeypatch.setattr(chat, 'get_hybrid_retriever', lambda: search)
    o = get_orchestrator()
    agent = o._agents[next(iter(o._agents))]
    async def answer(**kwargs):
        sources = kwargs['context']['rag_context']
        return AgentExecutionResult(success=True, output='证据不足' if not sources else '事实[来源1]')
    agent.execute = AsyncMock(side_effect=answer)
    with TestClient(app) as client:
        for chunks in ([], [{'content': '真实证据', 'metadata': {'page': 2, 'title': '公告'}}]):
            search.retrieve.return_value = chunks
            response = client.post('/api/v1/chat', json={'session_id': '', 'message': '分红', 'enable_rag': True})
            assert response.status_code == 200
            data = response.json()
            history = client.get('/api/v1/conversations/' + data['session_id']).json()['messages'][-1]
            assert history['content'] == data['message']
            assert history['sources'] == (data['sources'] or [])


def test_report_retrieval_failure_blocks_agents(monkeypatch):
    search = AsyncMock()
    search.retrieve.side_effect = RuntimeError('sensitive provider detail')
    monkeypatch.setattr(retriever, 'get_hybrid_retriever', lambda: search)
    o = get_orchestrator()
    o.run = AsyncMock()
    with TestClient(app) as client:
        response = client.post('/api/v1/reports', json={'stock_code': '600519', 'enable_rag': True})
        report = client.get('/api/v1/reports/' + response.json()['id']).json()
        assert report['status'] == 'failed'
        assert '检索服务暂不可用' in report['error']
        assert 'sensitive' not in report['error']
    o.run.assert_not_called()
    assert search.retrieve.call_args.kwargs['filters'] == {'stock_code': '600519'}


async def test_report_download_keeps_exact_citation_evidence():
    from app.models.schemas import AgentType
    o = get_orchestrator()
    sources = [{'citation': '来源1', 'label': '[来源1] 公告 页码:2\n来源:https://example.org',
                'content': '每股23.957元（含税）', 'metadata': {'page': 2}}]
    async def answer(**kwargs):
        assert kwargs['context']['rag_context'] == sources
        return AgentExecutionResult(success=True, output='分红23.957元[来源1]')
    for agent in o._agents.values():
        agent.execute = AsyncMock(side_effect=answer)
    result = await o.run('600519分红', agent_types=[AgentType.REPORT], context={'rag_context': sources})
    saved = o.store.get_report(result['report_id'])
    assert saved['sources'] == sources
    assert saved['content'] == result['final_response']
    assert sources[0]['label'] in saved['content'] and sources[0]['content'] in saved['content']
