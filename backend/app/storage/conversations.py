"""Transactional SQLite/PostgreSQL business store, including legacy SQLite history."""
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from functools import lru_cache
from sqlalchemy import create_engine, event, select, insert, update, delete, func
from sqlalchemy.engine import URL, make_url
from sqlalchemy.pool import NullPool
from app.config import get_settings
from app.storage.schema import metadata, versions, conversations, turns, reports, runs, documents


def now():
    return datetime.now(timezone.utc).isoformat()


def encode(value):
    return json.dumps(value, ensure_ascii=False)


class ArchivedConversation(ValueError):
    pass


class ConversationStore:
    def __init__(self, path=None, *, url=None):
        self.path = Path(path) if path else None
        if url:
            parsed = make_url(url)
            if parsed.drivername.startswith('postgresql'):
                parsed = parsed.set(drivername='postgresql+psycopg')
            if parsed.get_backend_name() not in ('postgresql', 'sqlite'):
                raise ValueError('仅支持 SQLite 或 PostgreSQL')
        else:
            if self.path is None:
                raise ValueError('需要指定数据库路径或 URL')
            self.path.parent.mkdir(parents=True, exist_ok=True)
            parsed = URL.create('sqlite', database=str(self.path))
        options = {'connect_args': {'check_same_thread': False, 'timeout': 10}} if parsed.get_backend_name() == 'sqlite' else {'connect_args': {'connect_timeout': 5}}
        self.engine = create_engine(parsed, poolclass=NullPool, **options)
        if parsed.get_backend_name() == 'sqlite':
            @event.listens_for(self.engine, 'connect')
            def foreign_keys(connection, _):
                connection.execute('PRAGMA foreign_keys=ON')
        self.upgrade()

    def upgrade(self):
        # Version 1 is additive: existing conversations/turns retain their IDs and payloads.
        with self.engine.begin() as db:
            if self.engine.dialect.name == 'postgresql':
                from sqlalchemy import text
                db.execute(text('SELECT pg_advisory_xact_lock(7413901)'))
            versions.create(db, checkfirst=True)
            version = db.scalar(select(func.max(versions.c.version))) or 0
            if version > 1:
                raise RuntimeError('数据库版本高于当前程序，请升级程序')
            if version < 1:
                metadata.create_all(db)
                db.execute(insert(versions).values(version=1))

    def _insert_ignore(self, db, table, values, key='id'):
        if self.engine.dialect.name == 'postgresql':
            from sqlalchemy.dialects.postgresql import insert as dialect_insert
        else:
            from sqlalchemy.dialects.sqlite import insert as dialect_insert
        db.execute(dialect_insert(table).values(**values).on_conflict_do_nothing(index_elements=[key]))

    def create(self, session_id=None, title='新对话'):
        session_id = session_id or str(uuid.uuid4())
        stamp = now()
        with self.engine.begin() as db:
            self._insert_ignore(db, conversations, dict(id=session_id, title=title, archived=0, created_at=stamp, updated_at=stamp))
        return self.get(session_id)

    def get(self, session_id):
        with self.engine.connect() as db:
            row = db.execute(select(conversations).where(conversations.c.id == session_id)).mappings().first()
        if row is None:
            raise KeyError(session_id)
        return {**row, 'archived': bool(row['archived'])}

    def list(self, archived=False):
        with self.engine.connect() as db:
            rows = db.execute(select(conversations).where(conversations.c.archived == int(archived)).order_by(conversations.c.updated_at.desc(), conversations.c.id)).mappings().all()
        return [{**row, 'archived': bool(row['archived'])} for row in rows]

    def turns(self, session_id, limit=None):
        query = select(turns.c.payload).where(turns.c.session_id == session_id)
        query = query.order_by(turns.c.id) if limit is None else query.order_by(turns.c.id.desc()).limit(limit)
        with self.engine.connect() as db:
            rows = list(db.scalars(query))
        return [json.loads(row) for row in (rows if limit is None else reversed(rows))]

    def _append(self, db, session_id, turn):
        row = db.execute(select(conversations).where(conversations.c.id == session_id).with_for_update()).mappings().first()
        if row is None:
            raise KeyError(session_id)
        if row['archived']:
            raise ArchivedConversation('请先恢复归档对话，再继续提问')
        first = db.scalar(select(turns.c.id).where(turns.c.session_id == session_id).limit(1)) is None
        db.execute(insert(turns).values(session_id=session_id, payload=encode(turn)))
        values = {'updated_at': now()}
        if first:
            values['title'] = ' '.join(turn['query'].split())[:40] or '新对话'
        db.execute(update(conversations).where(conversations.c.id == session_id).values(**values))

    def append(self, session_id, turn):
        with self.engine.begin() as db:
            self._append(db, session_id, turn)

    def archive(self, session_id, archived):
        self.get(session_id)
        with self.engine.begin() as db:
            db.execute(update(conversations).where(conversations.c.id == session_id).values(archived=int(archived)))
        return self.get(session_id)

    def delete(self, session_id):
        self.get(session_id)
        with self.engine.begin() as db:
            db.execute(delete(conversations).where(conversations.c.id == session_id))

    def clear(self, session_id):
        with self.engine.begin() as db:
            db.execute(delete(turns).where(turns.c.session_id == session_id))

    def start_run(self, run_id, session_id, query, report_id=None):
        with self.engine.begin() as db:
            db.execute(insert(runs).values(id=run_id, session_id=session_id, query=query, status='running', created_at=now(), updated_at=now()))
            if report_id:
                db.execute(update(reports).where(reports.c.id == report_id).values(run_id=run_id, status='running', updated_at=now()))

    def finish_run(self, run_id, result, turn=None, report_id=None):
        """Run, successful conversation turn and report commit together or roll back together."""
        success = result['success']
        with self.engine.begin() as db:
            if success and turn:
                self._append(db, result['session_id'], turn)
            values = dict(status='completed' if success else 'failed', payload=encode(result),
                          error=None if success else result['final_response'], updated_at=now())
            db.execute(update(runs).where(runs.c.id == run_id).values(**values))
            if report_id:
                db.execute(update(reports).where(reports.c.id == report_id).values(
                    status=values['status'], error=values['error'], updated_at=now(),
                    content=result['final_response'] if success else '',
                    sources=encode((turn or {}).get('response_metadata', {}).get('sources', []))))

    def fail_run(self, run_id, error, report_id=None):
        with self.engine.begin() as db:
            db.execute(update(runs).where(runs.c.id == run_id).values(status='failed', error=error, updated_at=now()))
            if report_id:
                db.execute(update(reports).where(reports.c.id == report_id).values(status='failed', error=error, updated_at=now()))

    def get_run(self, run_id):
        with self.engine.connect() as db:
            row = db.execute(select(runs).where(runs.c.id == run_id)).mappings().first()
        if row is None:
            raise KeyError(run_id)
        return {**row, 'payload': json.loads(row['payload'])}

    def create_report(self, title, stock_code, query, session_id, model):
        report_id = str(uuid.uuid4())
        with self.engine.begin() as db:
            db.execute(insert(reports).values(id=report_id, session_id=session_id, title=title,
                stock_code=stock_code, query=query, model=model, status='pending', created_at=now(), updated_at=now()))
        return self.get_report(report_id)

    def get_report(self, report_id):
        with self.engine.connect() as db:
            row = db.execute(select(reports).where(reports.c.id == report_id)).mappings().first()
        if row is None:
            raise KeyError(report_id)
        return {**row, 'sources': json.loads(row['sources'])}

    def list_reports(self):
        with self.engine.connect() as db:
            rows = db.execute(select(reports.c.id, reports.c.title, reports.c.stock_code, reports.c.status,
                reports.c.created_at, reports.c.updated_at, reports.c.error).order_by(reports.c.created_at.desc())).mappings().all()
        return [dict(row) for row in rows]

    def fail_report(self, report_id, error):
        with self.engine.begin() as db:
            db.execute(update(reports).where(reports.c.id == report_id).values(status='failed', error=error, updated_at=now()))

    def delete_report(self, report_id):
        with self.engine.begin() as db:
            row = db.execute(select(reports.c.status).where(reports.c.id == report_id).with_for_update()).first()
            if row is None:
                raise KeyError(report_id)
            if row[0] in ('pending', 'running'):
                raise ValueError('生成中的报告不能删除')
            db.execute(delete(reports).where(reports.c.id == report_id))

    def recover_interrupted(self):
        # Startup recovery is for the documented single-worker deployment.
        with self.engine.begin() as db:
            for table in (runs, reports):
                db.execute(update(table).where(table.c.status.in_(['pending', 'running'])).values(
                    status='failed', error='服务重启中断了生成，请重新提交', updated_at=now()))
            db.execute(update(documents).where(documents.c.status == 'indexing').values(
                status='failed', error='服务重启中断索引，请核对向量库后重新提交'))

    def save_document(self, doc_id, title, category, content_hash, payload, status, error=None):
        with self.engine.begin() as db:
            existing = db.scalar(select(documents.c.id).where(documents.c.id == doc_id))
            values = dict(title=title, category=category, content_hash=content_hash, payload=encode(payload), status=status, error=error)
            if existing:
                db.execute(update(documents).where(documents.c.id == doc_id).values(**values))
            else:
                db.execute(insert(documents).values(id=doc_id, created_at=now(), **values))

    def list_documents(self):
        with self.engine.connect() as db:
            rows = db.execute(select(documents).order_by(documents.c.created_at.desc())).mappings().all()
        return [{**row, 'payload': json.loads(row['payload'])} for row in rows]

    def get_document(self, doc_id):
        with self.engine.connect() as db:
            row = db.execute(select(documents).where(documents.c.id == doc_id)).mappings().first()
        if row is None:
            raise KeyError(doc_id)
        return {**row, 'payload': json.loads(row['payload'])}

    def delete_document(self, doc_id):
        with self.engine.begin() as db:
            db.execute(delete(documents).where(documents.c.id == doc_id))

    def import_history(self, source):
        """Atomic, insert-only import. Reject conflicting IDs rather than overwrite user data."""
        count = 0
        with self.engine.begin() as db:
            for item in source.list(False) + source.list(True):
                incoming = source.turns(item['id'])
                row = db.execute(select(conversations).where(conversations.c.id == item['id'])).mappings().first()
                if row:
                    current = list(db.scalars(select(turns.c.payload).where(turns.c.session_id == item['id']).order_by(turns.c.id)))
                    if dict(row) != {**item, 'archived': int(item['archived'])} or [json.loads(v) for v in current] != incoming:
                        raise ValueError('目标存在不同内容的同名会话，迁移已回滚')
                    continue
                db.execute(insert(conversations).values(**{**item, 'archived': int(item['archived'])}))
                for turn in incoming:
                    db.execute(insert(turns).values(session_id=item['id'], payload=encode(turn)))
                count += 1
        return count


@lru_cache()
def get_conversation_store():
    settings = get_settings()
    if settings.BUSINESS_STORAGE == 'postgresql':
        if make_url(settings.DATABASE_URL).get_backend_name() != 'postgresql':
            raise ValueError('PostgreSQL 模式需要 PostgreSQL DATABASE_URL')
        return ConversationStore(url=settings.DATABASE_URL)
    return ConversationStore(settings.CHAT_HISTORY_DB)
