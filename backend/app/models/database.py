"""
backend/app/models/database.py
SQLAlchemy ORM 模型 - PostgreSQL 数据库表定义
"""
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text, JSON, Index,
    ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100))
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    sessions = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")
    llm_calls = relationship("LLMCallLog", back_populates="user", cascade="all, delete-orphan")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(100), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(200), default="新对话")
    agent_types = Column(JSON, default=list)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_message = Column(Text)
    message_count = Column(Integer, default=0)

    user = relationship("User", back_populates="sessions")
    messages = relationship("ChatMessageDB", back_populates="session", cascade="all, delete-orphan")

    __table_args__ = (Index("idx_session_created", "session_id", "created_at"),)


class ChatMessageDB(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id"), nullable=False)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    agent_type = Column(String(50))
    token_count = Column(Integer, default=0)
    metadata = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("ChatSession", back_populates="messages")


class LLMCallLog(Base):
    """LLM 调用日志"""
    __tablename__ = "llm_call_logs"

    id = Column(Integer, primary_key=True, index=True)
    call_id = Column(String(100), unique=True, index=True, nullable=False)
    session_id = Column(String(100), index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    model = Column(String(50), nullable=False)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    latency_ms = Column(Float, default=0)
    cost_usd = Column(Float, default=0)
    success = Column(Boolean, default=True)
    error_message = Column(Text)
    prompt_preview = Column(Text)
    response_preview = Column(Text)
    metadata = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="llm_calls")

    __table_args__ = (
        Index("idx_llm_model_created", "model", "created_at"),
        Index("idx_llm_daily", "created_at"),
    )


class PromptVersionDB(Base):
    """Prompt 版本管理"""
    __tablename__ = "prompt_versions"

    id = Column(Integer, primary_key=True, index=True)
    version_id = Column(String(100), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    agent_type = Column(String(50))
    content = Column(Text, nullable=False)
    variables = Column(JSON, default=list)
    is_active = Column(Boolean, default=False)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class KnowledgeDocument(Base):
    """知识库文档"""
    __tablename__ = "knowledge_documents"

    id = Column(Integer, primary_key=True, index=True)
    doc_id = Column(String(100), unique=True, index=True, nullable=False)
    title = Column(String(500), nullable=False)
    category = Column(String(50), nullable=False)
    source = Column(String(200))
    content_hash = Column(String(64))
    metadata = Column(JSON, default=dict)
    chunk_count = Column(Integer, default=0)
    indexed = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    chunks = relationship("DocumentChunkDB", back_populates="document", cascade="all, delete-orphan")


class DocumentChunkDB(Base):
    """文档片段"""
    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, index=True)
    chunk_id = Column(String(100), unique=True, index=True, nullable=False)
    document_id = Column(Integer, ForeignKey("knowledge_documents.id"), nullable=False)
    content = Column(Text, nullable=False)
    chunk_index = Column(Integer, default=0)
    metadata = Column(JSON, default=dict)
    embedding_id = Column(String(200))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    document = relationship("KnowledgeDocument", back_populates="chunks")

    __table_args__ = (Index("idx_chunk_doc_index", "document_id", "chunk_index"),)


class DataPipeline(Base):
    """数据管道定义"""
    __tablename__ = "data_pipelines"

    id = Column(Integer, primary_key=True, index=True)
    pipeline_name = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    source_type = Column(String(50))
    schedule_cron = Column(String(100))
    is_active = Column(Boolean, default=True)
    config = Column(JSON, default=dict)
    last_run_at = Column(DateTime(timezone=True))
