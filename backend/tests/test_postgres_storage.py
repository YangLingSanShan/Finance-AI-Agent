"""Optional live PostgreSQL test; uses and removes a unique schema only."""
import os
import uuid
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from app.storage.conversations import ConversationStore


@pytest.mark.enable_socket
def test_postgresql_transactions_and_import(tmp_path):
    url = os.environ.get('TEST_DATABASE_URL')
    if not url:
        pytest.skip('设置 TEST_DATABASE_URL 后运行 PostgreSQL 集成测试')
    url = make_url(url).set(drivername='postgresql+psycopg')
    schema = 'agent_test_' + uuid.uuid4().hex
    admin = create_engine(url)
    target = None
    try:
        with admin.begin() as db:
            db.execute(text(f'CREATE SCHEMA {schema}'))
        scoped = url.update_query_dict({'options': f'-csearch_path={schema}'})
        target = ConversationStore(url=scoped)
        source = ConversationStore(tmp_path / 'source.sqlite3')
        source.create('saved')
        source.append('saved', {'query': '测试', 'final_response': '回答'})
        assert target.import_history(source) == 1
        assert target.turns('saved')[0]['final_response'] == '回答'
        report = target.create_report('报告', '600519', '测试', 'saved', 'test')
        target.start_run('run', 'saved', '测试', report['id'])
        target.finish_run('run', {'success': True, 'session_id': 'saved', 'final_response': '正文'},
                         {'query': '测试', 'final_response': '正文'}, report['id'])
        assert target.get_report(report['id'])['content'] == '正文'
        target.archive('saved', True)
        assert target.get('saved')['archived']
        target.delete('saved')
        assert target.turns('saved') == []
        assert target.get_report(report['id'])['content'] == '正文'
    finally:
        if target:
            target.engine.dispose()
        with admin.begin() as db:
            db.execute(text(f'DROP SCHEMA IF EXISTS {schema} CASCADE'))
        admin.dispose()
