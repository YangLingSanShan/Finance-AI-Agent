"""
backend/app/api/llmops.py
LLMOps 监控 API
"""
import logging
from fastapi import APIRouter, Query
from app.llmops.monitor import get_llmops_monitor

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/llmops/metrics")
async def get_metrics(days: int = Query(7, ge=1, le=90)):
    """获取 LLMOps 监控指标"""
    monitor = get_llmops_monitor()
    return monitor.get_metrics(days=days)


@router.get("/llmops/daily")
async def get_daily_stats(days: int = Query(30, ge=1, le=90)):
    """获取每日统计"""
    monitor = get_llmops_monitor()
    return {"daily_stats": monitor.get_daily_stats(days=days)}


@router.get("/llmops/recent")
async def get_recent_calls(limit: int = Query(50, ge=1, le=200)):
    """获取最近调用记录"""
    monitor = get_llmops_monitor()
    return {"recent_calls": monitor.get_recent_calls(limit=limit)}
