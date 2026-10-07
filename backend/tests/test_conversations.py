from unittest.mock import AsyncMock

from fastapi.testclient import TestClient
from app.main import app
from app.agents.orchestrator import AgentOrchestrator
from app.agents.base import AgentExecutionResult
from app.models.schemas import AgentType
from app.storage.conversations import ConversationStore, ArchivedConversation
import pytest


def test_history_api_lifecycle_and_cascade():
    with TestClient(app) as client:
        created = client.post('/api/v1/conversations')
        assert created.status_code == 201
        sid = created.json()['id']
        assert client.get('/api/v1/conversations').json()[0]['id'] == sid
        assert client.get(f'/api/v1/conversations/{sid}').json()['messages'] == []
        assert client.patch(f'/api/v1/conversations/{sid}', json={'archived': True}).status_code == 200
        assert client.get('/api/v1/conversations').json() == []
        assert client.get('/api/v1/conversations?archived=true').json()[0]['id'] == sid
        blocked = client.post('/api/v1/chat', json={'session_id': sid, 'message': '你好', 'enable_rag': False})
        assert blocked.status_code == 409
        assert client.patch(f'/api/v1/conversations/{sid}', json={'archived': False}).json()['archived'] is False
        assert client.delete(f'/api/v1/conversations/{sid}').status_code == 204
        assert client.get(f'/api/v1/conversations/{sid}').status_code == 404
        assert client.patch(f'/api/v1/conversations/{sid}', json={'archived': True}).status_code == 404
        assert client.delete(f'/api/v1/conversations/{sid}').status_code == 404


async def test_history_survives_restart_and_restores_model_context():
    first = AgentOrchestrator()
    first._agents[AgentType.RESEARCHER].execute = AsyncMock(return_value=AgentExecutionResult(success=True, output='记住了蓝鲸'))
    await first.run('暗号是蓝鲸', session_id='saved')
    restarted = AgentOrchestrator()
    model = AsyncMock(return_value=AgentExecutionResult(success=True, output='蓝鲸'))
    restarted._agents[AgentType.RESEARCHER].execute = model
    await restarted.run('暗号是什么', session_id='saved')
    assert any('蓝鲸' in str(m.content) for m in model.call_args.kwargs['history'])
    assert restarted.store.get('saved')['title'] == '暗号是蓝鲸'
    assert len(restarted.store.turns('saved')) == 2
    restarted.store.delete('saved')
    assert restarted.store.turns('saved') == []
    assert restarted.get_session_memory('saved') == []


async def test_archive_preserves_all_turns_beyond_context_window():
    orchestrator = AgentOrchestrator()
    orchestrator._agents[AgentType.RESEARCHER].execute = AsyncMock(return_value=AgentExecutionResult(success=True, output='回复'))
    for index in range(12):
        await orchestrator.run(f'第{index}轮', session_id='long')
    assert len(orchestrator.store.turns('long')) == 12
    assert len(orchestrator.get_session_memory('long')) == 10
    orchestrator.store.archive('long', True)
    with pytest.raises(ArchivedConversation):
        await orchestrator.run('归档中', session_id='long')
    assert len(orchestrator.store.turns('long')) == 12
    orchestrator.store.archive('long', False)
    await orchestrator.run('恢复后', session_id='long')
    assert len(orchestrator.store.turns('long')) == 13


def test_detail_preserves_messages_and_metadata():
    from app.agents.orchestrator import get_orchestrator
    store = get_orchestrator().store
    session = store.create()
    store.append(session['id'], {
        'query': '测试标题', 'final_response': '测试回复',
        'response_metadata': {'model': 'test', 'sources': [{'content': '证据', 'score': 0.9}],
                              'tool_calls': [{'name': 'add', 'result': '15', 'success': True}]},
    })
    with TestClient(app) as client:
        detail = client.get(f"/api/v1/conversations/{session['id']}").json()
    assert detail['title'] == '测试标题'
    assert [m['role'] for m in detail['messages']] == ['user', 'assistant']
    assert detail['messages'][1]['tool_calls'][0]['result'] == '15'
    assert detail['messages'][1]['sources'][0]['content'] == '证据'
    reopened = ConversationStore(store.path)
    assert reopened.get(session['id'])['title'] == '测试标题'
