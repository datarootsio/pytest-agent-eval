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


async def test_langchain_adapter_stringifies_unrecognised_result():
    """A chain ending in a plain str/StrOutputParser has neither .content nor 'messages'."""
    from pytest_agent_eval.adapters.langchain import LangChainAdapter

    runnable = MagicMock()
    runnable.ainvoke = AsyncMock(return_value="just a string")

    reply, tool_calls = await LangChainAdapter(runnable)([{"role": "user", "content": "hi"}])

    assert reply == "just a string"
    assert tool_calls == []


# --- system prompts ---


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


async def test_pydantic_ai_adapter_maps_system_role_to_system_prompt_part():
    """A system entry in history must become a SystemPromptPart, not a user prompt."""
    from pytest_agent_eval.adapters.pydantic_ai import _to_model_messages

    messages = _to_model_messages([{"role": "system", "content": "Be terse."}], ())

    assert [getattr(p, "part_kind", None) for m in messages for p in m.parts] == ["system-prompt"]


async def test_pydantic_ai_adapter_does_not_duplicate_an_existing_system_prompt():
    """History already opening with a system message must not gain a second copy."""
    from pytest_agent_eval.adapters.pydantic_ai import _to_model_messages

    messages = _to_model_messages(
        [{"role": "system", "content": "From history."}, {"role": "user", "content": "hi"}],
        ("From the agent.",),
    )

    system_parts = [p for m in messages for p in m.parts if getattr(p, "part_kind", None) == "system-prompt"]
    assert [p.content for p in system_parts] == ["From history."]
