-- 用戶表
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(100),
    is_active BOOLEAN DEFAULT true,
    is_superuser BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 对话会话
CREATE TABLE chat_sessions (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(100) UNIQUE NOT NULL,
    user_id INTEGER REFERENCES users(id),
    title VARCHAR(200) DEFAULT '新对话',
    agent_types JSONB DEFAULT '[]',
    message_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_session_created ON chat_sessions(session_id, created_at);

-- 消息记录
CREATE TABLE chat_messages (
    id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES chat_sessions(id),
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    agent_type VARCHAR(50),
    token_count INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- LLM 调用日志（重点表）
CREATE TABLE llm_call_logs (
    id SERIAL PRIMARY KEY,
    call_id VARCHAR(100) UNIQUE NOT NULL,
    session_id VARCHAR(100),
    user_id INTEGER REFERENCES users(id),
    model VARCHAR(50) NOT NULL,
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    latency_ms FLOAT DEFAULT 0,
    cost_usd FLOAT DEFAULT 0,
    success BOOLEAN DEFAULT true,
    error_message TEXT,
    prompt_preview TEXT,
    response_preview TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_llm_daily ON llm_call_logs(created_at);
CREATE INDEX idx_llm_model_created ON llm_call_logs(model, created_at);
CREATE INDEX idx_llm_session ON llm_call_logs(session_id);

-- 知识文档
CREATE TABLE knowledge_documents (
    id SERIAL PRIMARY KEY,
    doc_id VARCHAR(100) UNIQUE NOT NULL,
    title VARCHAR(500) NOT NULL,
    category VARCHAR(50) NOT NULL,
    source VARCHAR(200),
    content_hash VARCHAR(64),
    metadata JSONB DEFAULT '{}',
    chunk_count INTEGER DEFAULT 0,
    indexed BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 文档片段
CREATE TABLE document_chunks (
    id SERIAL PRIMARY KEY,
    chunk_id VARCHAR(100) UNIQUE NOT NULL,
    document_id INTEGER REFERENCES knowledge_documents(id),
    content TEXT NOT NULL,
    chunk_index INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    embedding_id VARCHAR(200),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_chunk_doc ON document_chunks(document_id, chunk_index);

-- 数据管道
CREATE TABLE data_pipelines (
    id SERIAL PRIMARY KEY,
    pipeline_name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    source_type VARCHAR(50),
    schedule_cron VARCHAR(100),
    is_active BOOLEAN DEFAULT true,
    config JSONB DEFAULT '{}',
    last_run_at TIMESTAMPTZ
);

-- 管道运行日志
CREATE TABLE data_pipeline_run_logs (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(100) UNIQUE NOT NULL,
    pipeline_name VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    records_processed INTEGER DEFAULT 0,
    records_failed INTEGER DEFAULT 0,
    error_message TEXT
);

-- Prompt 版本
CREATE TABLE prompt_versions (
    id SERIAL PRIMARY KEY,
    version_id VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    agent_type VARCHAR(50),
    content TEXT NOT NULL,
    variables JSONB DEFAULT '[]',
    is_active BOOLEAN DEFAULT false,
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 股票数据缓存
CREATE TABLE stock_cache (
    id SERIAL PRIMARY KEY,
    stock_code VARCHAR(10) NOT NULL,
    data_type VARCHAR(50) NOT NULL,
    data_date VARCHAR(20),
    data_json JSONB NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(stock_code, data_type, data_date)
);
CREATE INDEX idx_stock_cache_ttl ON stock_cache(stock_code, data_type, updated_at);
