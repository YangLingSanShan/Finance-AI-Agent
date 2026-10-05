"""
backend/app/llmops/monitor.py
LLMOps 监控模块 - 调用日志、成本追踪、指标暴露
"""
import time
import uuid
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict
from dataclasses import dataclass
from threading import Lock

logger = logging.getLogger(__name__)


@dataclass
class LLMCallRecord:
    call_id: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: float
    cost_usd: float
    success: bool
    error: Optional[str] = None
    session_id: Optional[str] = None
    prompt_preview: str = ""
    timestamp: str = ""


class LLMOpsMonitor:
    """
    LLMOps 监控器
    功能：全量记录LLM调用日志 | 实时计算Token消耗和成本
         统计成功率/平均延迟 | Prometheus指标暴露
    """

    def __init__(self):
        self._records: List[LLMCallRecord] = []
        self._daily_stats: Dict[str, Dict] = defaultdict(lambda: {
            "total_calls": 0, "total_tokens": 0, "total_cost": 0.0,
            "total_latency": 0.0, "success_calls": 0, "fail_calls": 0,
        })
        self._lock = Lock()
        self._max_records = 10000
        logger.info("[LLMOps] monitor initialized")

    def log_call(
        self, model: str, prompt_tokens: int, completion_tokens: int,
        total_tokens: int, latency_ms: float, cost_usd: float,
        success: bool, error: Optional[str] = None,
        session_id: Optional[str] = None,
        prompt_preview: str = "",
    ) -> str:
        call_id = str(uuid.uuid4())
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        today = timestamp[:10]

        record = LLMCallRecord(
            call_id=call_id, model=model, prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens, total_tokens=total_tokens,
            latency_ms=latency_ms, cost_usd=cost_usd, success=success,
            error=error, session_id=session_id, prompt_preview=prompt_preview[:100],
            timestamp=timestamp,
        )

        with self._lock:
            self._records.append(record)
            if len(self._records) > self._max_records:
                self._records = self._records[-self._max_records // 2:]

            stats = self._daily_stats[today]
            stats["total_calls"] += 1
            stats["total_tokens"] += total_tokens
            stats["total_cost"] += cost_usd
            stats["total_latency"] += latency_ms
            if success:
                stats["success_calls"] += 1
            else:
                stats["fail_calls"] += 1

        logger.debug(f"[LLMOps] log_call {model} tokens={total_tokens}")
        return call_id

    def get_metrics(self, days: int = 7) -> Dict[str, Any]:
        with self._lock:
            today = time.strftime("%Y-%m-%d")
            today_stats = self._daily_stats.get(today, {})

            totals = {"total_calls": 0, "total_tokens": 0, "total_cost": 0.0,
                       "total_latency": 0.0, "success_calls": 0, "fail_calls": 0}
            for d in range(days):
                day = (datetime.now() - timedelta(days=d)).strftime("%Y-%m-%d")
                stats = self._daily_stats.get(day, {})
                for k in totals:
                    totals[k] += stats.get(k, 0)

            total_calls = totals["total_calls"] or 1
            success_rate = totals["success_calls"] / total_calls
            today_calls = today_stats.get("total_calls", 0) or 1
            today_success_rate = today_stats.get("success_calls", 0) / today_calls

            return {
                "all_time": {
                    "total_calls": totals["total_calls"],
                    "total_tokens": totals["total_tokens"],
                    "total_cost_usd": round(totals["total_cost"], 6),
                    "avg_latency_ms": round(totals["total_latency"] / total_calls, 2),
                    "success_rate": round(success_rate * 100, 2),
                },
                "today": {
                    "calls": today_stats.get("total_calls", 0),
                    "tokens": today_stats.get("total_tokens", 0),
                    "cost_usd": round(today_stats.get("total_cost", 0), 6),
                    "avg_latency_ms": round(today_stats.get("total_latency", 0) / today_calls, 2),
                    "success_rate": round(today_success_rate * 100, 2),
                },
            }

    def get_daily_stats(self, days: int = 30) -> List[Dict]:
        result = []
        with self._lock:
            for d in range(days):
                day = (datetime.now() - timedelta(days=d)).strftime("%Y-%m-%d")
                stats = self._daily_stats.get(day, {})
                total_calls = stats.get("total_calls", 0) or 1
                result.append({
                    "date": day,
                    "calls": stats.get("total_calls", 0),
                    "tokens": stats.get("total_tokens", 0),
                    "cost_usd": round(stats.get("total_cost", 0), 6),
                    "avg_latency_ms": round(stats.get("total_latency", 0) / total_calls, 2),
                    "success_rate": round(stats.get("success_calls", 0) / total_calls * 100, 2),
                })
        return result[::-1]

    def get_recent_calls(self, limit: int = 50) -> List[Dict]:
        with self._lock:
            records = self._records[-limit:][::-1]
            return [{
                "call_id": r.call_id, "model": r.model, "tokens": r.total_tokens,
                "latency_ms": round(r.latency_ms, 2), "cost_usd": round(r.cost_usd, 6),
                "success": r.success, "error": r.error, "timestamp": r.timestamp,
            } for r in records]


llmops_monitor = LLMOpsMonitor()


def get_llmops_monitor() -> LLMOpsMonitor:
    return llmops_monitor
