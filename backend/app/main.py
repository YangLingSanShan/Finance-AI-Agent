"""
backend/app/main.py
FastAPI 应用入口
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.api import chat, agent, rag, llmops, data

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Financial AI Agent v{settings.APP_VERSION} starting...")
    logger.info(f"LLM: {settings.LLM_MODEL}, VectorStore: {settings.VECTORSTORE_TYPE}")
    yield
    logger.info("Financial AI Agent shutting down...")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="基于 LLM + Agent + RAG 的智能金融分析平台 API",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"[GlobalException] {str(exc)}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": str(exc)})


@app.get("/health")
async def health_check():
    return {"status": "healthy", "app": settings.APP_NAME, "version": settings.APP_VERSION,
            "llm_model": settings.LLM_MODEL}


@app.get("/")
async def root():
    return {"app": settings.APP_NAME, "version": settings.APP_VERSION, "docs": "/docs"}


# 注册路由
app.include_router(chat.router, prefix="/api/v1", tags=["对话"])
app.include_router(agent.router, prefix="/api/v1", tags=["Agent编排"])
app.include_router(rag.router, prefix="/api/v1", tags=["RAG知识库"])
app.include_router(llmops.router, prefix="/api/v1", tags=["LLMOps监控"])
app.include_router(data.router, prefix="/api/v1", tags=["金融数据"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT,
                reload=settings.DEBUG, workers=1, log_level="info")
