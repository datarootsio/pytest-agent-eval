"""TurnContext builders shared by the evaluator tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pytest_agent_eval.models import TurnContext

if TYPE_CHECKING:
    from collections.abc import Sequence


def turn_context(
    *,
    user: str = "test user",
    reply: str = "",
    tool_calls: Sequence[str] | None = None,
    history: list[dict] | None = None,
) -> TurnContext:
    """Build a TurnContext with everything but the field under test defaulted."""
    return TurnContext(
        user=user,
        reply=reply,
        tool_calls=list(tool_calls or []),
        history=history or [],
    )
