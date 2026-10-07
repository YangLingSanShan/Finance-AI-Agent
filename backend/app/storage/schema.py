"""Active business schema. Legacy models/database.py tables are not used by this store."""
from sqlalchemy import MetaData, Table, Column, String, Integer, Text, ForeignKey, Index

metadata = MetaData()
versions = Table('business_schema_version', metadata, Column('version', Integer, primary_key=True))
conversations = Table('conversations', metadata,
    Column('id', String(100), primary_key=True), Column('title', Text, nullable=False),
    Column('archived', Integer, nullable=False, default=0),
    Column('created_at', Text, nullable=False), Column('updated_at', Text, nullable=False))
turns = Table('conversation_turns', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('session_id', String(100), ForeignKey('conversations.id', ondelete='CASCADE'), nullable=False),
    Column('payload', Text, nullable=False))
Index('idx_turns_session', turns.c.session_id, turns.c.id)
runs = Table('agent_runs', metadata,
    Column('id', String(100), primary_key=True), Column('session_id', String(100), nullable=False, index=True),
    Column('status', String(20), nullable=False), Column('query', Text, nullable=False),
    Column('payload', Text, nullable=False, default='{}'), Column('error', Text),
    Column('created_at', Text, nullable=False), Column('updated_at', Text, nullable=False))
reports = Table('reports', metadata,
    Column('id', String(100), primary_key=True), Column('session_id', String(100), nullable=False),
    Column('run_id', String(100), ForeignKey('agent_runs.id'), unique=True),
    Column('title', Text, nullable=False), Column('stock_code', String(20), nullable=False),
    Column('query', Text, nullable=False), Column('status', String(20), nullable=False),
    Column('content', Text, nullable=False, default=''), Column('sources', Text, nullable=False, default='[]'),
    Column('model', Text, nullable=False), Column('error', Text),
    Column('created_at', Text, nullable=False), Column('updated_at', Text, nullable=False))
documents = Table('business_documents', metadata,
    Column('id', String(100), primary_key=True), Column('title', Text, nullable=False),
    Column('category', Text, nullable=False), Column('content_hash', String(64), nullable=False),
    Column('payload', Text, nullable=False), Column('status', String(20), nullable=False),
    Column('error', Text), Column('created_at', Text, nullable=False))
