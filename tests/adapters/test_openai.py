"""Tests for the raw OpenAI async-client adapter."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from pytest_agent_eval.models import ToolCall


async def test_openai_adapter_captures_tool_call_args():
    from pytest_agent_eval.adapters.openai import OpenAIAdapter

    tc = SimpleNamespace(function=SimpleNamespace(name="book_slot", arguments='{"time": "10am"}'))
    message = SimpleNamespace(content="done", tool_calls=[tc])
    response = SimpleNamespace(choices=[SimpleNamespace(message=message)])
    client = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=response)

    reply, tool_calls = await OpenAIAdapter(client, model="gpt-4o")([{"role": "user", "content": "hi"}])

    assert reply == "done"
    assert tool_calls == ["book_slot"]
    assert isinstance(tool_calls[0], ToolCall)
    assert tool_calls[0].args == {"time": "10am"}


async def test_openai_adapter_prepends_system_prompt():
    from pytest_agent_eval.adapters.openai import OpenAIAdapter

    message = SimpleNamespace(content="done", tool_calls=None)
    response = SimpleNamespace(choices=[SimpleNamespace(message=message)])
    client = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=response)

    await OpenAIAdapter(client, model="gpt-4o", system_prompt="Be terse.")([{"role": "user", "content": "hi"}])

    sent = client.chat.completions.create.await_args.kwargs["messages"]
    assert sent[0] == {"role": "system", "content": "Be terse."}
    assert sent[1]["content"] == "hi"
