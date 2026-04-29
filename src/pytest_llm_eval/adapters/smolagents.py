"""Adapter for smolagents agents (ToolCallingAgent, CodeAgent, ...)."""

from __future__ import annotations

import asyncio
from typing import Any


class SmolagentsAdapter:
    """Wrap a smolagents agent to conform to the agent callable contract.

    Duck-typed: works with any object exposing ``.run(task, reset=...)`` and
    ``.memory.steps``. Smolagents's sync ``run`` is offloaded with
    ``asyncio.to_thread`` so the event loop stays responsive.

    Args:
        agent: A smolagents agent (e.g. ``ToolCallingAgent``, ``CodeAgent``).
        include_internal_tools: When ``True``, smolagents-internal pseudo-tools
            (``python_interpreter``, ``final_answer``) are included in the
            returned tool-call list. Defaults to ``False``.

    Example:
        ```python
        from smolagents import ToolCallingAgent, InferenceClientModel
        from pytest_llm_eval.adapters.smolagents import SmolagentsAdapter

        model = InferenceClientModel(model_id="meta-llama/Llama-3.3-70B-Instruct")
        agent = ToolCallingAgent(tools=[...], model=model)

        @pytest.fixture
        def llm_eval_agent():
            return SmolagentsAdapter(agent)
        ```
    """

    def __init__(self, agent: Any, *, include_internal_tools: bool = False) -> None:
        """Store the smolagents agent and the internal-tool filter setting."""
        self._agent = agent
        self._include_internal_tools = include_internal_tools

    async def __call__(self, history: list[dict[str, Any]]) -> tuple[str, list[str]]:
        """Run the agent against the latest user message and return (reply, tool_calls)."""
        user_msg = history[-1]["content"] if history else ""
        reset = len(history) == 1
        result = await asyncio.to_thread(self._agent.run, user_msg, reset=reset)
        return str(result), []
