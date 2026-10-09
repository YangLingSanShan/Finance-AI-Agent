"""
backend/app/models/schemas.py
Pydantic 请求/响应数据模型
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Literal, Any, Dict
from datetime import datetime
from enum import Enum


class AgentType(str, Enum):
    RESEARCHER = "researcher"
    RISK = "risk"
    STRATEGIST = "strategist"
    REPORT = "report"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system", "tool"]
    content: str
    agent_type: Optional[AgentType] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: Optional[Dict[str, Any]] = None


class ChatRequest(BaseModel):
    session_id: str
    message: str = Field(..., min_length=1, max_length=4000)
    agent_type: Optional[AgentType] = None
    stream: bool = True
    enable_rag: bool = True


class ChatResponse(BaseModel):
    session_id: str
    message: str
    agent_type: AgentType
    sources: Optional[List[Dict[str, Any]]] = None
    token_usage: Optional[Dict[str, int]] = None
    latency_ms: Optional[float] = None
    model: str = ""
    report_id: Optional[str] = None
    session_created: bool = False
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)


class AgentInvokeRequest(BaseModel):
    session_id: str
    query: str
    agent_types: Optional[List[AgentType]] = None
    parallel: bool = True


class RAGQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)
    top_k: int = Field(default=10, ge=1, le=100)
    score_threshold: float = Field(default=0.5, ge=0, le=1)
    filters: Optional[Dict[str, Any]] = None
    enable_rerank: bool = True


class RAGQueryResponse(BaseModel):
    query: str
    chunks: List[Dict[str, Any]]
    total_retrieved: int
    rerank_applied: bool


class KnowledgeBaseUpload(BaseModel):
    title: str
    content: str
    category: str
    metadata: Optional[Dict[str, Any]] = None


class LLMCallRecord(BaseModel):
    call_id: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: float
    cost_usd: float
    success: bool
    timestamp: str


class LLMOpsMetrics(BaseModel):
    all_time: Dict[str, Any]
    today: Dict[str, Any]


class DataPipelineRun(BaseModel):
    run_id: str
    pipeline_name: str
    status: TaskStatus
    started_at: str
    completed_at: Optional[str] = None
    records_processed: int = 0
    records_failed: int = 0
    error_message: Optional[str] = None
