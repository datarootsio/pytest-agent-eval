"""Adapter for LangChain Runnable/Chain instances."""

from __future__ import annotations

from typing import Any


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

    def __init__(self, runnable: Any) -> None:
        """Store the LangChain runnable to delegate calls to."""
        self._runnable = runnable

    async def __call__(self, history: list[dict[str, Any]]) -> tuple[str, list[str]]:
        """Run the runnable and normalise output to (reply, tool_calls)."""
        result = await self._runnable.ainvoke({"messages": history})

        if hasattr(result, "content"):
            reply = str(result.content)
            tool_calls = [tc["name"] for tc in getattr(result, "tool_calls", []) or []]
        elif isinstance(result, dict) and "messages" in result:
            last = result["messages"][-1]
            reply = str(last.content)
            tool_calls = [tc["name"] for tc in getattr(last, "tool_calls", []) or []]
        else:
            reply = str(result)
            tool_calls = []

        return reply, tool_calls
