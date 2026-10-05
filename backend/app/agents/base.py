"""
backend/app/agents/base.py
Agent 基类 - 基于 LangChain 实现通用 Agent 框架
"""
import uuid
import time
import logging
from typing import Dict, Any, List, Optional, AsyncIterator
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

from langchain.schema import HumanMessage, SystemMessage, AIMessage, BaseMessage
from langchain.tools import BaseTool

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
    ) -> AgentExecutionResult:
        task_id = str(uuid.uuid4())
        start_time = time.time()
        total_tokens = 0

        logger.info(f"[Agent:{self.config.name}] executing task_id={task_id}")

        try:
            prompt_content = self._build_system_prompt()
            if context:
                context_str = self._format_context(context)
                prompt_content += f"\n\n## Context\n{context_str}"
            prompt_content += f"\n\n## Task\n{task}"

            messages = [
                SystemMessage(content=prompt_content),
                HumanMessage(content=task),
            ]

            tools_json = self._tools_to_json(self.config.tools)
            if tools_json:
                call_log = await self.llm.chat(messages=messages, tools=tools_json, stream=False)
                if not call_log.success:
                    raise Exception(f"LLM failed: {call_log.error}")
                total_tokens = call_log.total_tokens
                agent_output = f"[tools executed]\n{call_log.error or 'done'}"
            else:
                call_log = await self.llm.chat(messages=messages, stream=False)
                if not call_log.success:
                    raise Exception(f"LLM failed: {call_log.error}")
                total_tokens = call_log.total_tokens
                agent_output = str(call_log.error or "done")

            parsed = self._parse_output(agent_output)
            execution_time = (time.time() - start_time) * 1000

            self._execution_history.append({
                "task_id": task_id, "task": task, "output": agent_output,
                "parsed": parsed, "tokens": total_tokens,
                "execution_time_ms": execution_time,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            })

            return AgentExecutionResult(
                success=True, output=agent_output, iterations=1,
                total_tokens=total_tokens, execution_time_ms=execution_time,
            )

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error(f"[Agent:{self.config.name}] failed: {str(e)}", exc_info=True)
            return AgentExecutionResult(
                success=False, output="", error=str(e),
                iterations=0, total_tokens=total_tokens,
                execution_time_ms=execution_time,
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
            if isinstance(value, list):
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
        result = []
        for tool in tools:
            result.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            })
        return result

    def get_execution_history(self) -> List[Dict]:
        return self._execution_history

    def clear_history(self):
        self._execution_history.clear()
