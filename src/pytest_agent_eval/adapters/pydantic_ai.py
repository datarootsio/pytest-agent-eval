"""Adapter for pydantic-ai Agent instances."""

from __future__ import annotations

from typing import Any

from pytest_agent_eval.models import ToolCall

# Message parts that represent a tool call. pydantic-ai exposes provider-native
# (server-side) tool calls under a distinct part_kind; both carry args_as_dict().
_TOOL_CALL_PART_KINDS = frozenset({"tool-call", "builtin-tool-call"})


def _to_model_messages(history: list[dict[str, Any]]) -> list[Any]:
    """Convert OpenAI-style message dicts into pydantic-ai ModelMessage objects.

    pydantic-ai's ``message_history`` takes ``ModelMessage`` instances, not raw
    dicts (passing dicts raises ``AttributeError: 'dict' object has no attribute
    'conversation_id'`` on pydantic-ai 1.x+). User/system messages map to a
    ``ModelRequest``; assistant messages map to a ``ModelResponse``.
    """
    from pydantic_ai.messages import (
        ModelRequest,
        ModelResponse,
        SystemPromptPart,
        TextPart,
        UserPromptPart,
    )

    messages: list[Any] = []
    for msg in history:
        role = msg.get("role")
        content = msg.get("content", "")
        if role == "assistant":
            messages.append(ModelResponse(parts=[TextPart(content=content)]))
        elif role == "system":
            messages.append(ModelRequest(parts=[SystemPromptPart(content=content)]))
        else:
            messages.append(ModelRequest(parts=[UserPromptPart(content=content)]))
    return messages


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
        if not hasattr(agent, "run"):
            raise TypeError(
                f"PydanticAIAdapter expects a pydantic-ai Agent with an async .run() method, "
                f"got {type(agent).__name__}."
            )
        self._agent = agent

    async def __call__(self, history: list[dict[str, Any]]) -> tuple[str, list[str]]:
        """Run the agent and normalise output to (reply, tool_calls)."""
        user_msg = history[-1]["content"] if history else ""
        message_history = _to_model_messages(history[:-1])
        result = await self._agent.run(user_msg, message_history=message_history or None)

        tool_calls = [
            ToolCall(part.tool_name, part.args_as_dict())
            for msg in result.all_messages()
            for part in getattr(msg, "parts", [])
            if getattr(part, "part_kind", None) in _TOOL_CALL_PART_KINDS
        ]

        reply = result.output if isinstance(result.output, str) else str(result.output)
        return reply, tool_calls
