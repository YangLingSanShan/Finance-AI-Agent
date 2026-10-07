"""
backend/app/agents/base.py
Agent 基类 - 基于 LangChain 实现通用 Agent 框架
"""
import asyncio
import json
import uuid
import time
import logging
from typing import Dict, Any, List, Optional, AsyncIterator
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, BaseMessage, ToolMessage
from langchain.tools import BaseTool
from langchain_core.utils.function_calling import convert_to_openai_tool
from app.config import get_settings

from app.models.schemas import AgentType
from app.core.llm import LLMService, get_llm_service

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    name: str
    agent_type: AgentType
    description: str
    system_prompt: str
    tools: List[BaseTool] = field(default_factory=list)
    max_iterations: int = 10
    early_stop_threshold: float = 0.8
    temperature: float = 0.7


@dataclass
class AgentExecutionResult:
    success: bool
    output: str
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    iterations: int = 0
    total_tokens: int = 0
    execution_time_ms: float = 0.0
    error: Optional[str] = None


class BaseAgent(ABC):
    """
    Agent 基类 - 提供通用生命周期管理
    """

    def __init__(self, config: AgentConfig, llm_service: Optional[LLMService] = None):
        self.config = config
        self.llm = llm_service or get_llm_service()
        self._execution_history: List[Dict] = []
        self._memory: List[BaseMessage] = []
        self.system_prompt = SystemMessage(content=config.system_prompt)
        logger.info(f"[Agent] {config.name} initialized, tools={len(config.tools)}")

    @abstractmethod
    def _build_system_prompt(self) -> str:
        pass

    @abstractmethod
    def _parse_output(self, raw_output: str) -> Dict[str, Any]:
        pass

    async def execute(
        self, task: str,
        context: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
        history: Optional[List[BaseMessage]] = None,
    ) -> AgentExecutionResult:
        task_id = str(uuid.uuid4())
        start_time = time.time()
        total_tokens = 0
        iterations = 0
        trace = []
        try:
            prompt = self._build_system_prompt()
            if context:
                prompt += f"\n\n## Context\n{self._format_context(context)}"
            messages = [SystemMessage(content=prompt), *(history or []), HumanMessage(content=task)]
            tools_json = self._tools_to_json(self.config.tools)
            tools_by_name = {tool.name: tool for tool in self.config.tools}
            for iterations in range(1, self.config.max_iterations + 1):
                result = await self.llm.chat(list(messages), tools=tools_json or None, stream=False)
                total_tokens += result.total_tokens
                if not result.success:
                    raise RuntimeError(f"LLM failed: {result.error}")
                message = result.message or AIMessage(content=result.content)
                if message.invalid_tool_calls:
                    raise RuntimeError("模型返回了无效的工具参数，请重试")
                messages.append(message)
                if not message.tool_calls:
                    if not result.content.strip():
                        raise RuntimeError("模型未返回回答内容")
                    output = result.content
                    self._execution_history.append({
                        "task_id": task_id, "task": task, "output": output,
                        "parsed": self._parse_output(output), "tokens": total_tokens,
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    })
                    return AgentExecutionResult(
                        success=True, output=output, tool_calls=trace, iterations=iterations,
                        total_tokens=total_tokens, execution_time_ms=(time.time() - start_time) * 1000,
                    )
                for call in message.tool_calls:
                    name = call["name"]
                    record = {"id": call["id"], "name": name, "args": call["args"]}
                    try:
                        if name not in tools_by_name:
                            raise ValueError(f"未知工具: {name}")
                        value = await asyncio.wait_for(
                            tools_by_name[name].ainvoke(call["args"]),
                            timeout=get_settings().AGENT_TOOL_CALL_TIMEOUT,
                        )
                        content = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
                        record.update(success=True, result=content)
                    except Exception as exc:
                        error = "工具执行超时" if isinstance(exc, asyncio.TimeoutError) else str(exc)
                        content = json.dumps({"error": error}, ensure_ascii=False)
                        record.update(success=False, error=error)
                    trace.append(record)
                    messages.append(ToolMessage(content=content, tool_call_id=call["id"], name=name))
            raise RuntimeError(f"达到最大模型调用次数 ({self.config.max_iterations})，未获得最终回答")
        except Exception as exc:
            logger.warning("[Agent:%s] execution failed: %s", self.config.name, exc)
            return AgentExecutionResult(
                success=False, output="", error=str(exc), tool_calls=trace,
                iterations=iterations, total_tokens=total_tokens,
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    async def execute_stream(
        self, task: str, context: Optional[Dict[str, Any]] = None
    ) -> AsyncIterator[str]:
        prompt_content = self._build_system_prompt()
        if context:
            context_str = self._format_context(context)
            prompt_content += f"\n\n## Context\n{context_str}"
        prompt_content += f"\n\n## Task\n{task}"
        messages = [SystemMessage(content=prompt_content), HumanMessage(content=task)]
        full = ""
        async for token, _ in self.llm.chat_stream(messages):
            full += token
            yield token
        logger.info(f"[Agent:{self.config.name}] stream done, len={len(full)}")

    def _format_context(self, context: Dict[str, Any]) -> str:
        lines = []
        for key, value in context.items():
            if key == 'agent_results':
                continue  # Dependent outputs are provided in the explicit *_result fields.
            if key.endswith('_result'):
                lines.append(f"### {key}\n{value}")
            elif isinstance(value, list):
                lines.append(f"### {key}")
                for item in value:
                    if isinstance(item, dict):
                        lines.append(f"- {item.get('content', str(item))[:200]}")
                    else:
                        lines.append(f"- {str(item)[:200]}")
            elif isinstance(value, dict):
                lines.append(f"### {key}")
                for k, v in value.items():
                    lines.append(f"- {k}: {str(v)[:200]}")
            else:
                lines.append(f"**{key}**: {str(value)[:500]}")
        return "\n".join(lines)

    def _tools_to_json(self, tools: List[BaseTool]) -> List[Dict]:
        return [convert_to_openai_tool(tool) for tool in tools]

    def get_execution_history(self) -> List[Dict]:
        return self._execution_history

    def clear_history(self):
        self._execution_history.clear()
