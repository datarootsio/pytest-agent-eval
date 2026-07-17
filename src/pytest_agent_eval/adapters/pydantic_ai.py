"""Adapter for pydantic-ai Agent instances."""

from __future__ import annotations

from typing import Any

from pytest_agent_eval.models import ToolCall


class PydanticAIAdapter:
    """Wrap a pydantic-ai Agent to conform to the agent callable contract.

    Args:
        agent: A pydantic-ai ``Agent`` instance.

    Example:
        ```python
        from pydantic_ai import Agent
        from pytest_agent_eval.adapters.pydantic_ai import PydanticAIAdapter

        my_agent = Agent("openai:gpt-4o", system_prompt="You are helpful.")

        @pytest.fixture
        def llm_eval_agent():
            return PydanticAIAdapter(my_agent)
        ```
    """

    def __init__(self, agent: Any) -> None:
        """Store the pydantic-ai agent to delegate calls to."""
        self._agent = agent

    async def __call__(self, history: list[dict[str, Any]]) -> tuple[str, list[str]]:
        """Run the agent and normalise output to (reply, tool_calls)."""
        user_msg = history[-1]["content"] if history else ""
        message_history = history[:-1]
        result = await self._agent.run(user_msg, message_history=message_history)

        tool_calls = [
            ToolCall(part.tool_name, part.args_as_dict())
            for msg in result.all_messages()
            for part in getattr(msg, "parts", [])
            if getattr(part, "part_kind", None) == "tool-call"
        ]

        reply = result.output if isinstance(result.output, str) else str(result.output)
        return reply, tool_calls
