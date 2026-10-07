from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api import chat
from app.agents.base import AgentExecutionResult
from app.agents.orchestrator import AgentOrchestrator
from app.models.schemas import AgentType


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


def test_health_and_openapi(client):
    assert client.get('/health').json()['status'] == 'healthy'
    schema = client.get('/openapi.json').json()
    assert '/api/v1/chat' in schema['paths']
    assert '/api/v1/rag/query' in schema['paths']


@pytest.mark.parametrize('message', ['', 'x' * 4001])
def test_chat_rejects_invalid_message(client, message):
    response = client.post('/api/v1/chat', json={'session_id': 'test', 'message': message})
    assert response.status_code == 422


def test_chat_with_retrieved_context(client, monkeypatch):
    retriever = AsyncMock()
    retriever.retrieve.return_value = [
        {'content': '营收增长10%', 'score': 0.9, 'metadata': {'page': 3}}
    ]
    orchestrator = AsyncMock()
    orchestrator.run.return_value = {
        'final_response': '根据年报，营收增长10%。',
        'execution_summary': {'total_tokens': 12},
    }
    monkeypatch.setattr(chat, 'get_hybrid_retriever', lambda: retriever)
    monkeypatch.setattr(chat, 'get_orchestrator', lambda: orchestrator)
    response = client.post('/api/v1/chat', json={
        'session_id': 'test', 'message': '分析营收', 'enable_rag': True,
    })
    assert response.status_code == 200
    assert response.json()['message'] == '根据年报，营收增长10%。'
    assert response.json()['sources'][0]['metadata']['page'] == 3
    assert orchestrator.run.call_args.kwargs['context']['rag_context'][0]['score'] == 0.9


def test_chat_failure_is_reported(client, monkeypatch):
    orchestrator = AsyncMock()
    orchestrator.run.side_effect = RuntimeError('model unavailable')
    monkeypatch.setattr(chat, 'get_orchestrator', lambda: orchestrator)
    response = client.post('/api/v1/chat', json={
        'session_id': 'test', 'message': '分析', 'enable_rag': False,
    })
    assert response.status_code == 500
    assert response.json()['detail'] == 'model unavailable'


@pytest.mark.parametrize('top_k', [0, 101])
def test_rag_rejects_invalid_limit(client, top_k):
    response = client.post('/api/v1/rag/query', json={'query': '营收', 'top_k': top_k})
    assert response.status_code == 422


@pytest.mark.parametrize('parallel', [False, True])
async def test_orchestrator_aggregates_and_clears_memory(parallel):
    orchestrator = AgentOrchestrator()
    for agent_type, agent in orchestrator._agents.items():
        agent.execute = AsyncMock(return_value=AgentExecutionResult(
            success=True, output=f'{agent_type.value} result', total_tokens=3,
        ))
    result = await orchestrator.run(
        '综合分析', session_id='test', parallel=parallel,
        agent_types=[AgentType.RESEARCHER, AgentType.RISK],
    )
    assert result['execution_summary']['success_count'] == 2
    assert result['execution_summary']['total_tokens'] == 6
    assert 'risk result' in result['final_response']
    assert len(orchestrator.get_session_memory('test')) == 1
    orchestrator.clear_session('test')
    assert orchestrator.get_session_memory('test') == []


def test_orm_can_be_imported_and_mapped():
    from sqlalchemy.orm import configure_mappers
    from app.models.database import Base, ChatMessageDB, LLMCallLog, KnowledgeDocument, DocumentChunkDB
    configure_mappers()
    assert 'chat_messages' in Base.metadata.tables
    assert 'metadata' in Base.metadata.tables['chat_messages'].columns
    for model in (ChatMessageDB, LLMCallLog, KnowledgeDocument, DocumentChunkDB):
        assert model.metadata is Base.metadata


def test_agent_failure_returns_bad_gateway(client, monkeypatch):
    orchestrator = AsyncMock()
    orchestrator.run.return_value = {
        'success': False, 'final_response': '模型调用失败',
        'execution_summary': {'total_tokens': 0},
    }
    monkeypatch.setattr(chat, 'get_orchestrator', lambda: orchestrator)
    response = client.post('/api/v1/chat', json={
        'session_id': 'fail', 'message': '你好', 'enable_rag': False,
    })
    assert response.status_code == 502
    assert response.json()['detail'] == '模型调用失败'
