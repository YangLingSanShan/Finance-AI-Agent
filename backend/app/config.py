"""
backend/app/config.py
全局配置管理 - 使用 Pydantic Settings
"""
from pydantic_settings import BaseSettings
from typing import Optional
from functools import lru_cache


class Settings(BaseSettings):
    """应用全局配置"""

    # === 应用基础配置 ===
    APP_NAME: str = "Financial AI Agent"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    API_PREFIX: str = "/api/v1"

    # === FastAPI 服务配置 ===
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 4

    # === LLM 大模型配置 ===
    LLM_PROVIDER: str = "openai"
    LLM_MODEL: str = "qwen-plus"
    LLM_API_BASE: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    LLM_API_KEY: str = ""
    LLM_TEMPERATURE: float = 0.7
    LLM_MAX_TOKENS: int = 4096
    LLM_TIMEOUT: int = 120

    # === 嵌入模型配置 ===
    EMBEDDING_PROVIDER: str = "openai"
    EMBEDDING_MODEL: str = "text-embedding-3-large"
    EMBEDDING_API_BASE: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_BATCH_SIZE: int = 100
    EMBEDDING_DIM: int = 1536

    # === 数据库配置 ===
    DATABASE_URL: str = "postgresql+asyncpg://user:pass@localhost:5432/financial_agent"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10

    # === 向量数据库配置 ===
    VECTORSTORE_TYPE: str = "chroma"
    CHROMA_PERSIST_DIR: str = "./data/chromadb"
    CHROMA_COLLECTION_NAME: str = "financial_knowledge"

    # === Redis 配置 ===
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    REDIS_MAX_CONNECTIONS: int = 50

    # === RAG 配置 ===
    RAG_TOP_K: int = 10
    RAG_SCORE_THRESHOLD: float = 0.5
    RAG_RERANK_TOP_K: int = 5
    RAG_MAX_CONTEXT_LENGTH: int = 8000

    # === Agent 配置 ===
    AGENT_MAX_ITERATIONS: int = 10
    AGENT_EARLY_STOP_THRESHOLD: float = 0.8
    AGENT_TOOL_CALL_TIMEOUT: int = 30
    AGENT_MEMORY_TYPE: str = "buffer"

    # === DataOps 配置 ===
    DATAOPS_PREFECT_API: str = "http://localhost:4200/api"
    DATAOPS_WIND_TOKEN: str = ""
    DATAOPS_TUSHARE_TOKEN: str = ""
    DATAOPS_ETL_SCHEDULE_CRON: str = "0 2 * * *"

    # === LLMOps 配置 ===
    LLMOPS_PROMETHEUS_PORT: int = 9090
    LLMOPS_ENABLE_METRICS: bool = True
    LLMOPS_LOG_FILE: str = "./logs/llm_requests.log"

    # === 安全配置 ===
    SECRET_KEY: str = "change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "allow"


@lru_cache()
def get_settings() -> Settings:
    """获取单例配置实例"""
    return Settings()
