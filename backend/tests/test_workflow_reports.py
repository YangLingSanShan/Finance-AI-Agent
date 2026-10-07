import asyncio
import sqlite3
from unittest.mock import AsyncMock
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import app
from app.agents.orchestrator import AgentOrchestrator, OrchestratorConfig, get_orchestrator
from app.agents.base import AgentExecutionResult
from app.models.schemas import AgentType
from app.storage.conversations import ConversationStore, ArchivedConversation


def mock_roles(orchestrator, fail=None):
    for role, agent in orchestrator._agents.items():
        agent.execute = AsyncMock(return_value=AgentExecutionResult(
            success=role != fail, output=f'{role.value}完整内容' if role != fail else '',
            error='模拟失败' if role == fail else None))


@pytest.mark.parametrize('parallel', [False, True])
async def test_dependency_order_and_full_context(parallel):
    o = AgentOrchestrator()
    completed = set()
    async def execute(role, **kwargs):
        context = kwargs['context']
        if role == AgentType.STRATEGIST:
            assert {AgentType.RESEARCHER, AgentType.RISK} <= completed
            assert context['risk_result'] == 'risk' * 300
            assert context['researcher_result'] == 'researcher' * 300
        if role == AgentType.REPORT:
            assert AgentType.STRATEGIST in completed
            assert context['strategist_result'] == 'strategist' * 300
        await asyncio.sleep(0)
        completed.add(role)
        return AgentExecutionResult(success=True, output=role.value * 300)
    for role, agent in o._agents.items():
        async def call(role=role, **kw):
            return await execute(role, **kw)
        agent.execute = AsyncMock(side_effect=call)
    result = await o.run('生成600519报告', parallel=parallel)
    assert result['success']
    assert result['final_response'] == 'report' * 300
    saved = o.store.get_report(result['report_id'])
    assert saved['content'] == result['final_response']
    assert saved['status'] == 'completed'
    assert o.store.get_run(result['run_id'])['status'] == 'completed'


async def test_failure_blocks_strategy_and_report():
    o = AgentOrchestrator()
    mock_roles(o, AgentType.RISK)
    result = await o.run('完整报告')
    assert not result['success']
    o._agents[AgentType.STRATEGIST].execute.assert_not_called()
    o._agents[AgentType.REPORT].execute.assert_not_called()
    assert o.store.turns(result['session_id']) == []
    assert o.store.get_report(result['report_id'])['status'] == 'failed'
    assert o.store.get_run(result['run_id'])['payload']['agent_statuses']['risk']['error'] == '模拟失败'


async def test_global_concurrency_limit():
    o = AgentOrchestrator(OrchestratorConfig(max_parallel_agents=1))
    active = peak = 0
    async def execute(**kwargs):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(.01)
        active -= 1
        return AgentExecutionResult(success=True, output='结果')
    for agent in o._agents.values():
        agent.execute = execute
    await asyncio.gather(o.run('综合分析', session_id='one'), o.run('综合分析', session_id='two'))
    assert peak == 1


def test_intent_and_stock_codes():
    o = AgentOrchestrator()
    assert o._classify_intent('分析风险并生成报告') == 'report'
    assert o._classify_intent('风险评估') == 'stock_risk'
    assert o._classify_intent('ROE') == 'stock_analysis'
    assert o._extract_stock_codes('贵州茅台600519与300750，1234567') == ['600519', '300750']


def test_reports_api_lifecycle_and_reopen():
    o = get_orchestrator()
    mock_roles(o)
    with TestClient(app) as client:
        response = client.post('/api/v1/reports', json={'stock_code': '600519'})
        assert response.status_code == 202
        rid = response.json()['id']
        report = client.get(f'/api/v1/reports/{rid}').json()
        assert report['status'] == 'completed'
        assert report['content'] == 'report完整内容'
        assert client.get('/api/v1/reports').json()[0]['id'] == rid
        download = client.get(f'/api/v1/reports/{rid}/download')
        assert download.status_code == 200
        assert download.text == report['content']
        assert client.get(f"/api/v1/agent/runs/{report['run_id']}").json()['status'] == 'completed'
        reopened = ConversationStore(o.store.path)
        assert reopened.get_report(rid)['content'] == report['content']
        assert client.delete(f'/api/v1/reports/{rid}').status_code == 204
        assert client.get(f'/api/v1/reports/{rid}').status_code == 404
        assert client.post('/api/v1/reports', json={'stock_code': 'invalid'}).status_code == 422


def test_failed_report_cannot_download():
    mock_roles(get_orchestrator(), AgentType.RISK)
    with TestClient(app) as client:
        rid = client.post('/api/v1/reports', json={'stock_code': '600519'}).json()['id']
        assert client.get(f'/api/v1/reports/{rid}').json()['status'] == 'failed'
        assert client.get(f'/api/v1/reports/{rid}/download').status_code == 409


def test_running_report_and_restart_recovery():
    store = get_orchestrator().store
    session = store.create()
    report = store.create_report('标题', '600519', '问题', session['id'], 'test')
    store.start_run('interrupted', session['id'], '问题', report['id'])
    with pytest.raises(ValueError):
        store.delete_report(report['id'])
    reopened = ConversationStore(store.path)
    reopened.recover_interrupted()
    assert reopened.get_report(report['id'])['status'] == 'failed'
    assert reopened.get_run('interrupted')['status'] == 'failed'


def test_finish_transaction_rolls_back_on_history_failure():
    store = get_orchestrator().store
    session = store.create()
    report = store.create_report('标题', '', '问题', session['id'], 'test')
    store.start_run('rollback', session['id'], '问题', report['id'])
    store.archive(session['id'], True)
    with pytest.raises(ArchivedConversation):
        store.finish_run('rollback', {'success': True, 'session_id': session['id'], 'final_response': '正文'},
                         {'query': '问题'}, report['id'])
    assert store.get_run('rollback')['status'] == 'running'
    assert store.get_report(report['id'])['status'] == 'running'
    assert store.turns(session['id']) == []


def test_legacy_sqlite_upgrade_and_import_atomicity(tmp_path):
    source_path = tmp_path / 'old.sqlite3'
    with sqlite3.connect(source_path) as db:
        db.executescript('''CREATE TABLE conversations(id TEXT PRIMARY KEY,title TEXT NOT NULL,archived INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
        CREATE TABLE conversation_turns(id INTEGER PRIMARY KEY,session_id TEXT REFERENCES conversations(id) ON DELETE CASCADE,payload TEXT NOT NULL);
        INSERT INTO conversations VALUES ('legacy','旧标题',1,'2026','2026');
        INSERT INTO conversation_turns(session_id,payload) VALUES ('legacy','{"query":"旧问题","final_response":"旧回答"}');''')
    source = ConversationStore(source_path)
    target = ConversationStore(tmp_path / 'target.sqlite3')
    assert target.import_history(source) == 1
    assert target.get('legacy')['archived']
    assert target.turns('legacy')[0]['final_response'] == '旧回答'
    assert target.import_history(source) == 0
    source.create('new')
    source.archive('legacy', False)
    with pytest.raises(ValueError):
        target.import_history(source)
    with pytest.raises(KeyError):
        target.get('new')
    assert target.get('legacy')['archived']


def test_database_error_does_not_commit_turn(monkeypatch):
    store = get_orchestrator().store
    session = store.create()
    store.start_run('atomic', session['id'], '问题')
    original = store._append
    def fail_after_append(db, session_id, turn):
        original(db, session_id, turn)
        raise RuntimeError('database failure')
    monkeypatch.setattr(store, '_append', fail_after_append)
    with pytest.raises(RuntimeError):
        store.finish_run('atomic', {'success': True, 'session_id': session['id'], 'final_response': '正文'},
            {'query': '问题', 'final_response': '正文'})
    assert store.turns(session['id']) == []
    assert store.get_run('atomic')['status'] == 'running'


def test_document_metadata_is_saved_on_success_and_failure(monkeypatch):
    from app.api import rag
    from app.storage.schema import documents
    kb = AsyncMock()
    kb.add_text_chunks.return_value = 1
    monkeypatch.setattr(rag, 'get_kb_manager', lambda: kb)
    store = get_orchestrator().store
    with TestClient(app) as client:
        response = client.post('/api/v1/rag/knowledge/add', json={'title': '年报', 'category': 'report', 'content': '内容'})
        assert response.status_code == 200
        with store.engine.connect() as db:
            assert db.scalar(select(documents.c.status).where(documents.c.id == response.json()['doc_id'])) == 'indexed'
        kb.add_text_chunks.side_effect = RuntimeError('embedding unavailable')
        assert client.post('/api/v1/rag/knowledge/add', json={'title': '失败', 'category': 'report', 'content': '内容'}).status_code == 500
        with store.engine.connect() as db:
            assert db.scalar(select(documents.c.status).where(documents.c.title == '失败')) == 'failed'
