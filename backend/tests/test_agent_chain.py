import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain.tools import tool

from app.agents.base import AgentConfig, BaseAgent
from app.agents.orchestrator import AgentOrchestrator
from app.core.llm import LLMService, LLMCallLog
from app.models.schemas import AgentType


@tool
async def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b


class TestAgent(BaseAgent):
    __test__ = False

    def _build_system_prompt(self):
        return self.config.system_prompt

    def _parse_output(self, raw_output):
        return {'answer': raw_output}


def answer(content='', calls=None, success=True):
    return LLMCallLog(
        model='test', prompt_tokens=2, completion_tokens=3, total_tokens=5,
        latency_ms=1, cost_usd=0, timestamp='', success=success,
        error=None if success else 'model unavailable', content=content,
        message=AIMessage(content=content, tool_calls=calls or []),
    )


def make_agent(responses, tools=None, max_iterations=3):
    llm = SimpleNamespace(chat=AsyncMock(side_effect=responses))
    agent = TestAgent(AgentConfig(
        name='test', agent_type=AgentType.RESEARCHER, description='test',
        system_prompt='test', tools=tools or [], max_iterations=max_iterations,
    ), llm_service=llm)
    return agent, llm


def test_tool_schema_contains_required_parameters():
    agent, _ = make_agent([], [add])
    schema = agent._tools_to_json([add])[0]['function']['parameters']
    assert set(schema['required']) == {'a', 'b'}
    assert schema['properties']['a']['type'] == 'integer'


async def test_tool_loop_returns_real_answer_and_matching_tool_result():
    call = {'id': 'sum-1', 'name': 'add', 'args': {'a': 2, 'b': 3}}
    agent, llm = make_agent([answer(calls=[call]), answer('结果是5')], [add])
    result = await agent.execute('2+3等于多少？')
    assert result.success and result.output == '结果是5'
    assert result.iterations == 2 and result.total_tokens == 10
    assert result.tool_calls[0]['result'] == '5'
    messages = llm.chat.call_args_list[1].args[0]
    tool_message = next(m for m in messages if isinstance(m, ToolMessage))
    assert tool_message.tool_call_id == 'sum-1' and tool_message.content == '5'


@pytest.mark.parametrize('name,args', [('unknown', {}), ('add', {'a': 'bad', 'b': 3})])
async def test_tool_errors_are_returned_to_model(name, args):
    agent, llm = make_agent([
        answer(calls=[{'id': 'bad', 'name': name, 'args': args}]),
        answer('工具未能完成，无法确定结果'),
    ], [add])
    result = await agent.execute('问题')
    assert result.tool_calls[0]['success'] is False
    assert any(isinstance(m, ToolMessage) and 'error' in m.content
               for m in llm.chat.call_args.args[0])


async def test_iteration_limit_is_failure():
    call = {'id': 'loop', 'name': 'add', 'args': {'a': 1, 'b': 1}}
    agent, _ = make_agent([answer(calls=[call])], [add], max_iterations=1)
    result = await agent.execute('问题')
    assert not result.success and '最大' in result.error
    assert result.iterations == 1


@pytest.mark.parametrize('response', [answer(success=False), answer('')])
async def test_failed_or_empty_llm_response_is_not_done(response):
    agent, _ = make_agent([response])
    result = await agent.execute('问题')
    assert not result.success and result.output == ''


async def test_tool_timeout_is_returned_to_model(monkeypatch):
    @tool
    async def slow() -> str:
        """Slow tool."""
        await asyncio.sleep(1)
        return 'late'
    import app.agents.base as base
    monkeypatch.setattr(base, 'get_settings', lambda: SimpleNamespace(AGENT_TOOL_CALL_TIMEOUT=0.01))
    agent, _ = make_agent([
        answer(calls=[{'id': 'slow-1', 'name': 'slow', 'args': {}}]), answer('工具超时'),
    ], [slow])
    result = await agent.execute('问题')
    assert result.tool_calls[0]['error'] == '工具执行超时'


async def test_llm_preserves_content_tool_calls_and_usage():
    service = LLMService()
    message = AIMessage(content='真实回答', usage_metadata={
        'input_tokens': 7, 'output_tokens': 11, 'total_tokens': 18,
    })
    service._llm = SimpleNamespace(ainvoke=AsyncMock(return_value=message))
    result = await service.chat([HumanMessage(content='问题')])
    assert result.content == '真实回答' and result.message is message
    assert result.total_tokens == 18 and not result.usage_estimated


async def test_conversation_history_is_isolated_cleared_and_bounded():
    agent, llm = make_agent([answer('记住了'), answer('600519'), answer('没有历史'), answer('已清空')])
    orchestrator = AgentOrchestrator()
    orchestrator._agents = {AgentType.RESEARCHER: agent}
    await orchestrator.run('请记住600519', session_id='a')
    await orchestrator.run('刚才是什么代码？', session_id='a')
    second = llm.chat.call_args_list[1].args[0]
    assert any(isinstance(m, HumanMessage) and m.content == '请记住600519' for m in second)
    assert any(isinstance(m, AIMessage) and '记住了' in m.content for m in second)
    await orchestrator.run('刚才是什么代码？', session_id='b')
    assert len(llm.chat.call_args_list[2].args[0]) == 2
    orchestrator.clear_session('a')
    await orchestrator.run('还有历史吗', session_id='a')
    assert len(llm.chat.call_args_list[3].args[0]) == 2
    llm.chat.side_effect = None
    llm.chat.return_value = answer('回复')
    for _ in range(12):
        await orchestrator.run('下一轮', session_id='a')
    assert len(orchestrator.get_session_memory('a')) == 10


async def test_failed_turn_is_not_saved():
    agent, _ = make_agent([answer(success=False)])
    orchestrator = AgentOrchestrator()
    orchestrator._agents = {AgentType.RESEARCHER: agent}
    result = await orchestrator.run('问题', session_id='failed')
    assert not result['success']
    assert orchestrator.get_session_memory('failed') == []


async def test_same_session_concurrent_turns_are_ordered():
    agent, llm = make_agent([answer('第一轮'), answer('第二轮')])
    orchestrator = AgentOrchestrator()
    orchestrator._agents = {AgentType.RESEARCHER: agent}
    await asyncio.gather(orchestrator.run('第一问', session_id='same'),
                         orchestrator.run('第二问', session_id='same'))
    assert any(isinstance(m, AIMessage) and '第一轮' in m.content
               for m in llm.chat.call_args_list[1].args[0])


async def test_deepseek_wire_request_and_response_without_network():
    import json
    import httpx
    from app.config import Settings
    requests = []

    def respond(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={
            'id': 'test', 'object': 'chat.completion', 'created': 0,
            'model': 'deepseek-flash',
            'choices': [{'index': 0, 'finish_reason': 'stop',
                         'message': {'role': 'assistant', 'content': '已接通'}}],
            'usage': {'prompt_tokens': 2, 'completion_tokens': 3, 'total_tokens': 5},
        })

    service = LLMService()
    service.settings = Settings(_env_file=None, LLM_MODEL='deepseek-flash',
                                LLM_API_KEY='test-key', LLM_API_BASE='https://example.invalid')
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        from langchain_openai import ChatOpenAI
        # Use the production constructor, supplying only the mock transport.
        import unittest.mock
        original = ChatOpenAI
        with unittest.mock.patch('app.core.llm.ChatOpenAI', side_effect=lambda **kw: original(http_async_client=client, **kw)):
            result = await service.chat([HumanMessage(content='你好')])
    assert result.success and result.content == '已接通' and result.total_tokens == 5
    assert requests[0]['thinking'] == {'type': 'disabled'}
    assert requests[0]['stream'] is False


def test_chat_api_tool_trace_followup_and_clear(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.api import chat, agent as agent_api
    call = {'id': 'api-sum', 'name': 'add', 'args': {'a': 7, 'b': 8}}
    agent, llm = make_agent([answer(calls=[call]), answer('15'), answer('上次是15')], [add])
    orchestrator = AgentOrchestrator()
    orchestrator._agents = {AgentType.RESEARCHER: agent}
    monkeypatch.setattr(chat, 'get_orchestrator', lambda: orchestrator)
    monkeypatch.setattr(agent_api, 'get_orchestrator', lambda: orchestrator)
    with TestClient(app) as client:
        first = client.post('/api/v1/chat', json={
            'session_id': 'api', 'message': '计算7+8', 'enable_rag': False,
        })
        assert first.status_code == 200
        assert '15' in first.json()['message']
        assert first.json()['tool_calls'][0]['result'] == '15'
        second = client.post('/api/v1/chat', json={
            'session_id': 'api', 'message': '上次结果是什么', 'enable_rag': False,
        })
        assert second.status_code == 200
        assert any(isinstance(m, AIMessage) and '15' in m.content
                   for m in llm.chat.call_args.args[0])
        assert client.delete('/api/v1/agent/memory/api').status_code == 200
        assert client.get('/api/v1/agent/memory/api').json()['conversation_turns'] == 0
