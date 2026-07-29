from pytest_agent_eval.models import Message

"""Tests for the LangChain Runnable adapter."""

from unittest.mock import AsyncMock, MagicMock

import pytest


class _FakeAIMessage:
    def __init__(self, content: str, tool_calls: list[dict]) -> None:
        self.content = content
        self.tool_calls = tool_calls


async def test_langchain_adapter_captures_args_from_message_result() -> None:
    from pytest_agent_eval.adapters.langchain import LangChainAdapter

    msg = _FakeAIMessage("done", [{"name": "book_slot", "args": {"time": "10am"}}])
    runnable = MagicMock()
    runnable.ainvoke = AsyncMock(return_value=msg)

    reply, tool_calls = await LangChainAdapter(runnable)([Message(role="user", content="hi")])

    assert reply == "done"
    assert tool_calls[0] == "book_slot"
    assert tool_calls[0].args == {"time": "10am"}


async def test_langchain_adapter_captures_args_from_graph_result() -> None:
    from pytest_agent_eval.adapters.langchain import LangChainAdapter

    msg = _FakeAIMessage("done", [{"name": "book_slot", "args": {"time": "10am"}}])
    runnable = MagicMock()
    runnable.ainvoke = AsyncMock(return_value={"messages": [msg]})

    reply, tool_calls = await LangChainAdapter(runnable)([Message(role="user", content="hi")])

    assert reply == "done"
    assert tool_calls[0].args == {"time": "10am"}


async def test_langchain_adapter_handles_missing_args_key() -> None:
    from pytest_agent_eval.adapters.langchain import LangChainAdapter

    msg = _FakeAIMessage("done", [{"name": "book_slot"}])
    runnable = MagicMock()
    runnable.ainvoke = AsyncMock(return_value=msg)

    _, tool_calls = await LangChainAdapter(runnable)([Message(role="user", content="hi")])

    assert tool_calls[0] == "book_slot"
    assert tool_calls[0].args is None


@pytest.mark.parametrize("shape", ["message", "graph"], ids=["direct_message", "graph_result"])
async def test_langchain_adapter_treats_tool_calls_of_none_as_no_tools(shape: str) -> None:
    """LangChain sets ``tool_calls`` to None as well as omitting it.

    The ``or []`` covers None; without it this raises TypeError. Both branches of
    ``__call__`` read the attribute independently, so both need pinning.
    """
    from pytest_agent_eval.adapters.langchain import LangChainAdapter

    msg = _FakeAIMessage("done", None)  # type: ignore[arg-type]
    runnable = MagicMock()
    runnable.ainvoke = AsyncMock(return_value=msg if shape == "message" else {"messages": [msg]})

    reply, tool_calls = await LangChainAdapter(runnable)([Message(role="user", content="hi")])

    assert reply == "done"
    assert tool_calls == []


async def test_langchain_adapter_stringifies_unrecognised_result() -> None:
    """A chain ending in a plain str/StrOutputParser has neither .content nor 'messages'."""
    from pytest_agent_eval.adapters.langchain import LangChainAdapter

    runnable = MagicMock()
    runnable.ainvoke = AsyncMock(return_value="just a string")

    reply, tool_calls = await LangChainAdapter(runnable)([Message(role="user", content="hi")])

    assert reply == "just a string"
    assert tool_calls == []


@pytest.mark.parametrize(
    "result",
    [
        pytest.param({"output": "no messages key"}, id="dict_without_messages"),
        pytest.param({"messages": []}, id="empty_messages_list"),
        pytest.param({"messages": "not a list"}, id="messages_not_a_list"),
    ],
)
async def test_langchain_adapter_stringifies_a_graph_result_it_cannot_read(result: dict) -> None:
    """Each hop into a graph result is checked separately, and any of them may fail.

    The empty and non-list cases used to raise (IndexError, then AttributeError) because a
    cast asserted the whole shape while only the outer dict was checked.
    """
    from pytest_agent_eval.adapters.langchain import LangChainAdapter

    runnable = MagicMock()
    runnable.ainvoke = AsyncMock(return_value=result)

    reply, tool_calls = await LangChainAdapter(runnable)([Message(role="user", content="hi")])

    assert reply == str(result)
    assert tool_calls == []
