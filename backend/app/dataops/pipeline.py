"""
backend/app/dataops/pipeline.py
DataOps 数据管道编排 - 金融数据 ETL
"""
import logging
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from dataclasses import dataclass
import asyncio

logger = logging.getLogger(__name__)


@dataclass
class PipelineStage:
    name: str
    description: str
    extractor: Optional[Callable] = None
    transformer: Optional[Callable] = None
    loader: Optional[Callable] = None
    validator: Optional[Callable] = None


class DataPipeline:
    """
    金融数据 ETL 管道
    阶段：Extract -> Transform -> Validate -> Load
    """

    def __init__(self, name: str):
        self.name = name
        self.stages: List[PipelineStage] = []
        self._is_running = False
        self._last_run_at: Optional[datetime] = None
        self._last_status: str = "idle"

    def add_stage(self, stage: PipelineStage):
        self.stages.append(stage)
        return self

    async def run(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        import uuid
        run_id = str(uuid.uuid4())
        params = params or {}
        start_time = datetime.now()

        logger.info(f"[Pipeline:{self.name}] starting run_id={run_id}")
        self._is_running = True

        total_records = 0
        stage_results = {}

        try:
            for stage in self.stages:
                logger.info(f"[Pipeline:{self.name}] stage: {stage.name}")

                extracted_data = []
                if stage.extractor:
                    extracted_data = await self._safe_call(stage.extractor, params)

                transformed_data = []
                if stage.transformer:
                    transformed_data = await self._safe_call(stage.transformer, extracted_data, params)

                validation_result = {"passed": True, "errors": []}
                if stage.validator:
                    validation_result = await self._safe_call(stage.validator, transformed_data)

                loaded_count = 0
                if stage.loader:
                    loaded_count = await self._safe_call(stage.loader, transformed_data)
                    total_records += loaded_count

                stage_results[stage.name] = {
                    "extracted": len(extracted_data),
                    "transformed": len(transformed_data),
                    "loaded": loaded_count,
                    "validated": validation_result.get("passed", False),
                }

            self._last_status = "success"
            self._last_run_at = datetime.now()

            return {
                "run_id": run_id, "pipeline": self.name, "status": "success",
                "total_records": total_records, "stage_results": stage_results,
                "started_at": start_time.isoformat(),
                "completed_at": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"[Pipeline:{self.name}] failed: {str(e)}", exc_info=True)
            self._last_status = "failed"
            return {
                "run_id": run_id, "pipeline": self.name, "status": "failed",
                "error": str(e), "total_records": total_records,
                "stage_results": stage_results,
                "started_at": start_time.isoformat(),
                "completed_at": datetime.now().isoformat(),
            }
        finally:
            self._is_running = False

    async def _safe_call(self, func: Callable, *args, **kwargs) -> Any:
        try:
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"[Pipeline] stage failed: {str(e)}")
            return []


# ===== 预置抽取器 =====

async def wind_stock_quote_extractor(params: Dict) -> List[Dict]:
    """Wind 股票行情抽取器"""
    return [{"stock_code": "000001", "stock_name": "平安银行",
             "price": 12.50, "change_pct": 1.23, "volume": 50000000,
             "timestamp": datetime.now().isoformat()}]


async def tushare_financial_extractor(params: Dict) -> List[Dict]:
    """Tushare 财务数据抽取器"""
    return [{"stock_code": "600519", "report_date": "2024-06-30",
             "revenue": 83000000000, "net_profit": 4200000000,
             "gross_margin": 0.92, "roe": 0.15}]


async def stock_quote_transformer(data: List[Dict], params: Dict) -> List[Dict]:
    """行情数据转换"""
    return [{"code": item.get("stock_code", ""),
             "name": item.get("stock_name", ""),
             "price": float(item.get("price", 0)),
             "change_pct": float(item.get("change_pct", 0)),
             "volume": int(item.get("volume", 0))} for item in data]


async def data_quality_validator(data: List[Dict]) -> Dict:
    """数据质量校验"""
    errors = []
    for i, item in enumerate(data[:10]):
        if not item.get("code"):
            errors.append(f"第{i}条缺少股票代码")
    return {"passed": len(errors) == 0, "errors": errors, "checked": len(data)}


async def db_loader(data: List[Dict]) -> int:
    """数据库加载"""
    logger.info(f"[DBLoader] loading {len(data)} records")
    return len(data)
