"""Adapter for LangChain Runnable/Chain instances."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, cast

from pytest_agent_eval.adapters._args import coerce_args
from pytest_agent_eval.models import AgentReply, History, ToolCall

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence


class _AIMessage(Protocol):
    """A LangChain message, as read off a runnable's result."""

    content: object


class LangChainRunnable(Protocol):
    """The slice of a LangChain Runnable the adapter uses: one async invocation."""

    async def ainvoke(self, payload: Mapping[str, object], /) -> object:
        """Invoke the runnable on a ``{"messages": [...]}`` state."""
        ...


def _tool_calls(message: object) -> list[ToolCall]:
    """Read LangChain's ``tool_calls`` off a message; absent means no tools were called."""
    return [ToolCall(tc["name"], coerce_args(tc.get("args"))) for tc in getattr(message, "tool_calls", []) or []]


class LangChainAdapter:
    """Wrap a LangChain Runnable to conform to the agent callable contract.

    Expects the runnable to accept ``{"messages": [...]}`` and return an
    ``AIMessage`` or object with a ``content`` attribute.

    Args:
        runnable: A LangChain Runnable (e.g. a compiled graph or chain).

    Example:
        ```python
        from pytest_agent_eval.adapters.langchain import LangChainAdapter

        @pytest.fixture
        def llm_eval_agent():
            return LangChainAdapter(my_langchain_graph)
        ```
    """

    def __init__(self, runnable: object) -> None:
        """Store the LangChain runnable to delegate calls to."""
        # `object`, not the Protocol: a structural type here would reject the very SDK
        # class the docstring says we wrap (verified — a real AsyncOpenAI is not
        # assignable to it). The hasattr guard below is the real check, and it raises a
        # message naming the extra; the Protocol types what we call after narrowing.
        if not hasattr(runnable, "ainvoke"):
            raise TypeError(
                f"LangChainAdapter expects a LangChain Runnable with an .ainvoke() method, "
                f"got {type(runnable).__name__}. Wrap a compiled graph or chain, and make sure "
                "the extra is installed: pip install 'pytest-agent-eval[langchain]'"
            )
        self._runnable = cast("LangChainRunnable", runnable)

    async def __call__(self, history: History) -> AgentReply:
        """Run the runnable and normalise output to (reply, tool_calls)."""
        # Plain dicts, not Messages: langchain_core.convert_to_messages() raises
        # NotImplementedError on a Mapping that is not a dict.
        result = await self._runnable.ainvoke({"messages": [m.to_dict() for m in history]})

        if hasattr(result, "content"):
            return AgentReply(str(result.content), _tool_calls(result))
        if isinstance(result, dict) and "messages" in result:
            last = cast("Mapping[str, Sequence[_AIMessage]]", result)["messages"][-1]
            return AgentReply(str(last.content), _tool_calls(last))
        return AgentReply(str(result), [])
