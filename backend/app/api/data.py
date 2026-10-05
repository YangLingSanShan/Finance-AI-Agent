"""
backend/app/api/data.py
金融数据查询 API
"""
import logging
from fastapi import APIRouter, HTTPException
from app.dataops.pipeline import DataPipeline, PipelineStage, wind_stock_quote_extractor

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/data/stock/{stock_code}")
async def get_stock_info(stock_code: str):
    """查询股票基本信息"""
    return {
        "code": stock_code, "name": f"股票{stock_code}",
        "industry": "未知行业", "market": "主板",
        "listing_date": "2010-01-01",
    }


@router.get("/data/stock/{stock_code}/quote")
async def get_stock_quote(stock_code: str):
    """查询股票实时行情"""
    return {
        "code": stock_code, "name": f"股票{stock_code}",
        "price": 12.50, "change_pct": 1.23, "volume": 50000000,
        "high": 12.80, "low": 12.30, "open": 12.35,
        "timestamp": "2024-01-01 09:30:00",
    }


@router.post("/data/pipeline/run")
async def run_data_pipeline(pipeline_name: str = "stock_quote"):
    """手动触发数据管道"""
    pipeline = DataPipeline(name=pipeline_name)
    pipeline.add_stage(PipelineStage(
        name="extract", description="extract stock data",
        extractor=wind_stock_quote_extractor,
    ))
    return await pipeline.run()
