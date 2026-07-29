from pytest_agent_eval.models import Message

"""Tests for the pydantic-ai adapter."""

from unittest.mock import AsyncMock, MagicMock


async def test_pydantic_ai_adapter_extracts_tool_calls_from_message_parts() -> None:
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

    reply, tool_calls = await PydanticAIAdapter(agent)([Message(role="user", content="book me")])

    assert reply == "Booked!"
    assert tool_calls == ["book_slot"]
    assert tool_calls[0].args == {"time": "10am"}


async def test_pydantic_ai_adapter_maps_system_role_to_system_prompt_part() -> None:
    """A system entry in history must become a SystemPromptPart, not a user prompt."""
    from pytest_agent_eval.adapters.pydantic_ai import _to_model_messages

    messages = _to_model_messages([Message(role="system", content="Be terse.")], ())

    assert [getattr(p, "part_kind", None) for m in messages for p in m.parts] == ["system-prompt"]


async def test_pydantic_ai_adapter_does_not_duplicate_an_existing_system_prompt() -> None:
    """History already opening with a system message must not gain a second copy."""
    from pytest_agent_eval.adapters.pydantic_ai import _to_model_messages

    messages = _to_model_messages(
        [Message(role="system", content="From history."), Message(role="user", content="hi")],
        ("From the agent.",),
    )

    system_parts = [p for m in messages for p in m.parts if getattr(p, "part_kind", None) == "system-prompt"]
    assert [p.content for p in system_parts] == ["From history."]
