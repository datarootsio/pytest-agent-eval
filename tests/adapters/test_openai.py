"""Tests for the raw OpenAI async-client adapter."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from pytest_agent_eval.adapters.openai import OpenAIAdapter
from pytest_agent_eval.models import Message, ToolCall


async def test_openai_adapter_captures_tool_call_args() -> None:
    from pytest_agent_eval.adapters.openai import OpenAIAdapter

    # `type` is not optional padding: the SDK's tool_calls is a discriminated union, and it
    # is what tells a function call apart from a custom one.
    tc = SimpleNamespace(type="function", function=SimpleNamespace(name="book_slot", arguments='{"time": "10am"}'))
    message = SimpleNamespace(content="done", tool_calls=[tc])
    response = SimpleNamespace(choices=[SimpleNamespace(message=message)])
    client = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=response)

    reply, tool_calls = await OpenAIAdapter(client, model="gpt-4o")([Message(role="user", content="hi")])

    assert reply == "done"
    assert tool_calls == ["book_slot"]
    assert isinstance(tool_calls[0], ToolCall)
    assert tool_calls[0].args == {"time": "10am"}


async def test_openai_adapter_captures_a_custom_tool_call() -> None:
    """A custom tool call has .custom, not .function — reading .function raised AttributeError."""
    tc = SimpleNamespace(type="custom", custom=SimpleNamespace(name="run_sql", input='{"query": "select 1"}'))
    message = SimpleNamespace(content="done", tool_calls=[tc])
    client = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=SimpleNamespace(choices=[SimpleNamespace(message=message)]))

    _, tool_calls = await OpenAIAdapter(client, model="gpt-4o")([Message(role="user", content="hi")])

    assert tool_calls == ["run_sql"]
    assert tool_calls[0].args == {"query": "select 1"}


async def test_openai_adapter_reports_free_text_custom_input_as_uncaptured() -> None:
    """A custom tool's input is free text; only JSON can become an args mapping."""
    tc = SimpleNamespace(type="custom", custom=SimpleNamespace(name="run_sql", input="select 1"))
    message = SimpleNamespace(content="done", tool_calls=[tc])
    client = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=SimpleNamespace(choices=[SimpleNamespace(message=message)]))

    _, tool_calls = await OpenAIAdapter(client, model="gpt-4o")([Message(role="user", content="hi")])

    assert tool_calls == ["run_sql"]
    assert tool_calls[0].args is None


async def test_openai_adapter_sends_each_role_as_the_sdks_own_param_type() -> None:
    """The SDK types `messages` per role, so the adapter dispatches instead of using to_dict()."""
    message = SimpleNamespace(content="done", tool_calls=None)
    client = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=SimpleNamespace(choices=[SimpleNamespace(message=message)]))

    await OpenAIAdapter(client, model="gpt-4o")(
        [
            Message(role="user", content="hi"),
            Message(role="assistant", content="hello"),
            Message(role="system", content="be terse"),
        ]
    )

    sent = client.chat.completions.create.await_args.kwargs["messages"]
    assert sent == [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
        {"role": "system", "content": "be terse"},
    ]


async def test_openai_adapter_prepends_system_prompt() -> None:
    from pytest_agent_eval.adapters.openai import OpenAIAdapter

    message = SimpleNamespace(content="done", tool_calls=None)
    response = SimpleNamespace(choices=[SimpleNamespace(message=message)])
    client = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=response)

    await OpenAIAdapter(client, model="gpt-4o", system_prompt="Be terse.")([Message(role="user", content="hi")])

    sent = client.chat.completions.create.await_args.kwargs["messages"]
    assert sent[0] == Message(role="system", content="Be terse.")
    assert sent[1]["content"] == "hi"


async def test_plugin_internal_audio_key_is_not_sent_to_the_api() -> None:
    """runner.py sets audio on every voice turn; the chat API rejects unknown message keys."""
    message = SimpleNamespace(content="done", tool_calls=None)
    client = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=SimpleNamespace(choices=[SimpleNamespace(message=message)]))

    await OpenAIAdapter(client, model="gpt-4o")([Message(role="user", content="hi", audio="turn1.wav")])

    sent = client.chat.completions.create.await_args.kwargs["messages"]
    assert sent == [{"role": "user", "content": "hi"}]
    assert all(isinstance(m, dict) for m in sent), "the SDK serialises the body as JSON"
