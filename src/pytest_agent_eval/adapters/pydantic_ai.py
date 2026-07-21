"""Adapter for pydantic-ai Agent instances."""

from __future__ import annotations

from typing import Any

from pytest_agent_eval.models import ToolCall

# Message parts that represent a tool call. pydantic-ai exposes provider-native
# (server-side) tool calls under a distinct part_kind; both carry args_as_dict().
_TOOL_CALL_PART_KINDS = frozenset({"tool-call", "builtin-tool-call"})


def _is_tool_call_part(part: Any) -> bool:
    if getattr(part, "part_kind", None) not in _TOOL_CALL_PART_KINDS:
        return False
    # Native tool-*search* parts share the 'builtin-tool-call' kind but represent
    # the model searching its own tool catalogue, not an external invocation.
    return "Search" not in type(part).__name__


def _static_system_prompts(agent: Any) -> tuple[str, ...]:
    """Best-effort read of an Agent's static ``system_prompt=`` strings.

    pydantic-ai only re-applies a configured system prompt when ``message_history``
    is empty; with a reconstructed history we must re-embed it ourselves or every
    turn after the first runs without it. ``instructions=`` are re-applied each run
    by pydantic-ai regardless, and dynamic ``@agent.system_prompt`` functions can't
    be recovered here — those degrade to the pre-fix behaviour rather than crash.
    """
    prompts = getattr(agent, "_system_prompts", ())
    return tuple(prompts) if isinstance(prompts, (tuple, list)) else ()


def _to_model_messages(history: list[dict[str, Any]], system_prompts: tuple[str, ...]) -> list[Any]:
    """Convert OpenAI-style message dicts into pydantic-ai ModelMessage objects.

    pydantic-ai's ``message_history`` takes ``ModelMessage`` instances, not raw
    dicts (passing dicts raises ``AttributeError: 'dict' object has no attribute
    'conversation_id'`` on pydantic-ai 1.x+). User/system messages map to a
    ``ModelRequest``; assistant messages map to a ``ModelResponse``. The agent's
    static system prompt is prepended to the first request so it survives across
    turns.
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

    if system_prompts and messages and isinstance(messages[0], ModelRequest):
        already_has_system = any(getattr(p, "part_kind", None) == "system-prompt" for p in messages[0].parts)
        if not already_has_system:
            messages[0].parts = [SystemPromptPart(content=sp) for sp in system_prompts] + list(messages[0].parts)

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
        message_history = _to_model_messages(history[:-1], _static_system_prompts(self._agent))
        result = await self._agent.run(user_msg, message_history=message_history or None)

        tool_calls = [
            ToolCall(part.tool_name, part.args_as_dict())
            for msg in result.all_messages()
            for part in getattr(msg, "parts", [])
            if _is_tool_call_part(part)
        ]

        reply = result.output if isinstance(result.output, str) else str(result.output)
        return reply, tool_calls
