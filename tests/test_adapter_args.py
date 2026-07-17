"""Tests for tool-call argument capture across adapters."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from pytest_agent_eval.adapters._args import coerce_args
from pytest_agent_eval.models import ToolCall

# --- coerce_args ---


def test_coerce_args_passes_dict_through():
    assert coerce_args({"a": 1}) == {"a": 1}


def test_coerce_args_parses_json_string():
    assert coerce_args('{"date": "tomorrow"}') == {"date": "tomorrow"}


def test_coerce_args_returns_none_for_invalid_json():
    assert coerce_args("{not json") is None


def test_coerce_args_returns_none_for_non_dict_json():
    assert coerce_args("[1, 2]") is None


def test_coerce_args_returns_none_for_other_types():
    assert coerce_args(None) is None
    assert coerce_args(42) is None


# --- OpenAIAdapter ---


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


# --- constructor guards ---


def test_adapter_constructors_reject_wrong_objects():
    import pytest

    from pytest_agent_eval.adapters.langchain import LangChainAdapter
    from pytest_agent_eval.adapters.openai import OpenAIAdapter
    from pytest_agent_eval.adapters.pydantic_ai import PydanticAIAdapter
    from pytest_agent_eval.adapters.smolagents import SmolagentsAdapter

    with pytest.raises(TypeError, match=r"ainvoke.*pytest-agent-eval\[langchain\]"):
        LangChainAdapter("not a runnable")
    with pytest.raises(TypeError, match=r"chat\.completions.*pytest-agent-eval\[openai\]"):
        OpenAIAdapter("not a client", model="gpt-4o")
    with pytest.raises(TypeError, match=r"pydantic-ai Agent"):
        PydanticAIAdapter("not an agent")
    with pytest.raises(TypeError, match=r"memory\.steps.*pytest-agent-eval\[smolagents\]"):
        SmolagentsAdapter("not an agent")


# --- PydanticAIAdapter ---


async def test_pydantic_ai_adapter_extracts_tool_calls_from_message_parts():
    """Regression: modern pydantic-ai messages carry tool calls in .parts, not .tool_name."""
    from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart

    from pytest_agent_eval.adapters.pydantic_ai import PydanticAIAdapter

    response = ModelResponse(
        parts=[
            ToolCallPart(tool_name="book_slot", args={"time": "10am"}),
            TextPart(content="Booked!"),
        ]
    )
    mock_result = MagicMock()
    mock_result.output = "Booked!"
    mock_result.all_messages.return_value = [response]
    agent = MagicMock()
    agent.run = AsyncMock(return_value=mock_result)

    reply, tool_calls = await PydanticAIAdapter(agent)([{"role": "user", "content": "book me"}])

    assert reply == "Booked!"
    assert tool_calls == ["book_slot"]
    assert tool_calls[0].args == {"time": "10am"}


# --- LangChainAdapter ---


class _FakeAIMessage:
    def __init__(self, content: str, tool_calls: list[dict]):
        self.content = content
        self.tool_calls = tool_calls


async def test_langchain_adapter_captures_args_from_message_result():
    from pytest_agent_eval.adapters.langchain import LangChainAdapter

    msg = _FakeAIMessage("done", [{"name": "book_slot", "args": {"time": "10am"}}])
    runnable = MagicMock()
    runnable.ainvoke = AsyncMock(return_value=msg)

    reply, tool_calls = await LangChainAdapter(runnable)([{"role": "user", "content": "hi"}])

    assert reply == "done"
    assert tool_calls[0] == "book_slot"
    assert tool_calls[0].args == {"time": "10am"}


async def test_langchain_adapter_captures_args_from_graph_result():
    from pytest_agent_eval.adapters.langchain import LangChainAdapter

    msg = _FakeAIMessage("done", [{"name": "book_slot", "args": {"time": "10am"}}])
    runnable = MagicMock()
    runnable.ainvoke = AsyncMock(return_value={"messages": [msg]})

    reply, tool_calls = await LangChainAdapter(runnable)([{"role": "user", "content": "hi"}])

    assert reply == "done"
    assert tool_calls[0].args == {"time": "10am"}


async def test_langchain_adapter_handles_missing_args_key():
    from pytest_agent_eval.adapters.langchain import LangChainAdapter

    msg = _FakeAIMessage("done", [{"name": "book_slot"}])
    runnable = MagicMock()
    runnable.ainvoke = AsyncMock(return_value=msg)

    _, tool_calls = await LangChainAdapter(runnable)([{"role": "user", "content": "hi"}])

    assert tool_calls[0] == "book_slot"
    assert tool_calls[0].args is None
