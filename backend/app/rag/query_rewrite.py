"""
backend/app/rag/query_rewrite.py
查询改写模块 - 通过 LLM 优化用戶查询
"""
import re
import json
import logging
from typing import Dict, Any
from app.core.llm import get_llm_service

logger = logging.getLogger(__name__)


class QueryRewriter:
    """
    查询改写器
    功能：意图澄清 | 同义词扩展 | 查询分解 | 格式修正
    """

    REWRITE_PROMPT = """你是专业金融搜索查询优化助手。
原始查询：{original_query}

请优化查询：
1. 术语标准化："茅台" -> "贵州茅台(600519)"
2. 意图识别：投研分析 / ⻛险评估 / 策略建议 / 知识问答
3. 查询扩展（可选）：补充同义词

JSON格式输出：
{{"rewritten_query": "优化后查询", "intent": "意图", "stock_codes": [], "stock_names": [], "notes": ""}}
只输出JSON，不要其他内容。"""

    def __init__(self):
        self.llm = get_llm_service()

    async def rewrite(self, query: str) -> Dict[str, Any]:
        try:
            from langchain.schema import HumanMessage
            messages = [HumanMessage(content=self.REWRITE_PROMPT.format(original_query=query))]
            log = await self.llm.chat(messages, stream=False)
            result_text = log.error or "{}"
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', result_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
            return {"rewritten_query": query, "intent": "unknown", "stock_codes": [], "stock_names": [], "expand_queries": []}
        except Exception as e:
            logger.warning(f"[QueryRewrite] failed: {str(e)}")
            return {"rewritten_query": query, "intent": "unknown", "stock_codes": [], "stock_names": [], "expand_queries": []}
