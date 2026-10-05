"""
backend/app/core/llm.py
LLM 大模型统一调用接口 - 支持多模型供应商
"""
import time
import logging
from typing import Optional, AsyncIterator, Any, Dict, List
from dataclasses import dataclass

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain.schema import BaseMessage, HumanMessage, SystemMessage

from app.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class LLMCallLog:
    """LLM 调用日志"""
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: float
    cost_usd: float
    timestamp: str
    success: bool
    error: Optional[str] = None


class TokenCostCalculator:
    """Token 成本计算器"""

    GPT4O_INPUT = 0.0025 / 1000
    GPT4O_OUTPUT = 0.01 / 1000
    QWEN_INPUT = 0.001 / 1000
    QWEN_OUTPUT = 0.002 / 1000
    DEEPSEEK_INPUT = 0.001 / 1000
    DEEPSEEK_OUTPUT = 0.002 / 1000

    @classmethod
    def calculate(cls, model: str, input_tokens: int, output_tokens: int) -> float:
        model_lower = model.lower()
        if "gpt-4o" in model_lower or "gpt-4" in model_lower:
            return input_tokens * cls.GPT4O_INPUT + output_tokens * cls.GPT4O_OUTPUT
        elif "qwen" in model_lower:
            return input_tokens * cls.QWEN_INPUT + output_tokens * cls.QWEN_OUTPUT
        elif "deepseek" in model_lower:
            return input_tokens * cls.DEEPSEEK_INPUT + output_tokens * cls.DEEPSEEK_OUTPUT
        return 0.0


class LLMService:
    """LLM 大模型统一服务接口"""

    def __init__(self):
        self.settings = get_settings()
        self._llm: Optional[ChatOpenAI] = None
        self._embeddings: Optional[OpenAIEmbeddings] = None

    @property
    def llm(self) -> ChatOpenAI:
        """延迟初始化 LLM 客戶端"""
        if self._llm is None:
            self._llm = ChatOpenAI(
                model=self.settings.LLM_MODEL,
                api_key=self.settings.LLM_API_KEY,
                base_url=self.settings.LLM_API_BASE,
                temperature=self.settings.LLM_TEMPERATURE,
                max_tokens=self.settings.LLM_MAX_TOKENS,
                timeout=self.settings.LLM_TIMEOUT,
                streaming=True,
            )
        return self._llm

    @property
    def embeddings(self) -> OpenAIEmbeddings:
        """延迟初始化 Embedding 客戶端"""
        if self._embeddings is None:
            self._embeddings = OpenAIEmbeddings(
                model=self.settings.EMBEDDING_MODEL,
                api_key=self.settings.EMBEDDING_API_KEY,
                base_url=self.settings.EMBEDDING_API_BASE,
                batch_size=self.settings.EMBEDDING_BATCH_SIZE,
            )
        return self._embeddings

    async def chat(
        self,
        messages: List[BaseMessage],
        tools: Optional[List[Dict]] = None,
        tool_choice: Optional[str] = None,
        stream: bool = True,
    ) -> LLMCallLog:
        """通用对话接口"""
        start_time = time.time()

        try:
            if tools:
                response = await self.llm.bind_tools(tools).ainvoke(messages)
            else:
                response = await self.llm.ainvoke(messages)

            latency = (time.time() - start_time) * 1000

            usage = getattr(response, "usage", None)
            if usage:
                prompt_tokens = getattr(usage, "prompt_tokens", 0)
                completion_tokens = getattr(usage, "completion_tokens", 0)
                total_tokens = getattr(usage, "total_tokens", 0)
            else:
                prompt_tokens = sum(len(str(m.content)) for m in messages) // 4
                completion_tokens = len(str(response.content)) // 4
                total_tokens = prompt_tokens + completion_tokens

            cost = TokenCostCalculator.calculate(
                self.settings.LLM_MODEL, prompt_tokens, completion_tokens
            )

            log = LLMCallLog(
                model=self.settings.LLM_MODEL,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                latency_ms=latency,
                cost_usd=cost,
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
                success=True,
            )

            logger.info(
                f"[LLM] model={self.settings.LLM_MODEL} tokens={total_tokens} "
                f"latency={latency:.0f}ms cost=${cost:.6f}"
            )
            return log

        except Exception as e:
            latency = (time.time() - start_time) * 1000
            logger.error(f"[LLM] 调用失败: {str(e)}")
            return LLMCallLog(
                model=self.settings.LLM_MODEL,
                prompt_tokens=0, completion_tokens=0, total_tokens=0,
                latency_ms=latency, cost_usd=0.0,
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
                success=False, error=str(e),
            )

    async def chat_stream(
        self, messages: List[BaseMessage]
    ) -> AsyncIterator[tuple[str, Optional[LLMCallLog]]]:
        """流式对话"""
        start_time = time.time()
        full_response = ""

        try:
            async for chunk in self.llm.astream(messages):
                token = chunk.content if hasattr(chunk, "content") else str(chunk)
                full_response += token
                yield token, None

            latency = (time.time() - start_time) * 1000
            prompt_tokens = sum(len(str(m.content)) for m in messages) // 4
            completion_tokens = len(full_response) // 4
            total_tokens = prompt_tokens + completion_tokens
            cost = TokenCostCalculator.calculate(
                self.settings.LLM_MODEL, prompt_tokens, completion_tokens
            )

            log = LLMCallLog(
                model=self.settings.LLM_MODEL,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                latency_ms=latency,
                cost_usd=cost,
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
                success=True,
            )
            yield "", log

        except Exception as e:
            latency = (time.time() - start_time) * 1000
            log = LLMCallLog(
                model=self.settings.LLM_MODEL,
                prompt_tokens=0, completion_tokens=0, total_tokens=0,
                latency_ms=latency, cost_usd=0.0,
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
                success=False, error=str(e),
            )
            yield "", log

    async def embed(self, texts: List[str]) -> List[List[float]]:
        """文本向量化"""
        try:
            embeddings = await self.embeddings.aembed_documents(texts)
            logger.info(f"[Embedding] texts={len(texts)} dim={len(embeddings[0]) if embeddings else 0}")
            return embeddings
        except Exception as e:
            logger.error(f"[Embedding] 失败: {str(e)}")
            raise


llm_service = LLMService()


def get_llm_service() -> LLMService:
    return llm_service
