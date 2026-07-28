from pytest_agent_eval.models import Message

"""Tests for the LangChain Runnable adapter."""

from unittest.mock import AsyncMock, MagicMock


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


async def test_langchain_adapter_stringifies_unrecognised_result() -> None:
    """A chain ending in a plain str/StrOutputParser has neither .content nor 'messages'."""
    from pytest_agent_eval.adapters.langchain import LangChainAdapter

    runnable = MagicMock()
    runnable.ainvoke = AsyncMock(return_value="just a string")

    reply, tool_calls = await LangChainAdapter(runnable)([Message(role="user", content="hi")])

    assert reply == "just a string"
    assert tool_calls == []
