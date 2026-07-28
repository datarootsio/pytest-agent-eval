"""Adapter for LangChain Runnable/Chain instances."""

from __future__ import annotations

from typing import Protocol

from pytest_agent_eval.adapters._args import coerce_args
from pytest_agent_eval.models import AgentReply, History, ToolCall


class LangChainRunnable(Protocol):
    """The slice of a LangChain Runnable the adapter uses: one async invocation.

    ``payload`` is a ``dict``, not a ``Mapping``: a real ``Runnable[dict[str, object], ...]``
    accepts only a dict, so a Protocol promising to accept any Mapping is one the real class
    cannot satisfy. It is also what the adapter actually passes, for the reason in
    ``__call__``.
    """

    async def ainvoke(self, payload: dict[str, object], /) -> object:
        """Invoke the runnable on a ``{"messages": [...]}`` state."""
        ...


def _tool_calls(message: object) -> list[ToolCall]:
    """Read LangChain's ``tool_calls`` off a message; absent means no tools were called."""
    return [ToolCall(tc["name"], coerce_args(tc.get("args"))) for tc in getattr(message, "tool_calls", []) or []]


def _last_message(result: object) -> object | None:
    """The final message of a graph-shaped ``{"messages": [...]}`` result, if it is one.

    Every hop is checked, because each can fail independently: the result may not be a
    mapping, may not carry ``messages``, and that value may not be a non-empty list. The
    cast this replaced asserted all three while checking only the first.
    """
    if not isinstance(result, dict):
        return None
    messages = result.get("messages")
    if not isinstance(messages, list) or not messages:
        return None
    return messages[-1]


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

    def __init__(self, runnable: LangChainRunnable) -> None:
        """Store the LangChain runnable to delegate calls to."""
        # The Protocol is on the parameter, so a type checker rejects a wrong object at the
        # call site. The guard is for callers without one: it names the extra to install,
        # which an assignability error does not.
        if not hasattr(runnable, "ainvoke"):
            raise TypeError(
                f"LangChainAdapter expects a LangChain Runnable with an .ainvoke() method, "
                f"got {type(runnable).__name__}. Wrap a compiled graph or chain, and make sure "
                "the extra is installed: pip install 'pytest-agent-eval[langchain]'"
            )
        self._runnable = runnable

    async def __call__(self, history: History) -> AgentReply:
        """Run the runnable and normalise output to (reply, tool_calls)."""
        # Plain dicts, not Messages: langchain_core.convert_to_messages() raises
        # NotImplementedError on a Mapping that is not a dict.
        result = await self._runnable.ainvoke({"messages": [m.to_dict() for m in history]})

        if hasattr(result, "content"):
            return AgentReply(str(result.content), _tool_calls(result))
        last = _last_message(result)
        if last is not None:
            return AgentReply(str(getattr(last, "content", "")), _tool_calls(last))
        return AgentReply(str(result), [])
