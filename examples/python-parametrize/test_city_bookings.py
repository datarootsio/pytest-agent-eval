from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from pytest_agent_eval import Expect, Turn

if TYPE_CHECKING:
    from pytest_agent_eval.runner import EvalSession


@pytest.mark.parametrize("city", ["Ghent", "Leuven"])
@pytest.mark.agent_eval(threshold=1.0, runs=1)
async def test_booking_mentions_city(agent_eval: EvalSession, city: str) -> None:
    # Deterministic mock agent; replace with your real agent or an adapter.
    async def agent(history):
        return f"Booked a table in {city}! Reference BK-1234.", ["create_booking"]

    result = await agent_eval.run(
        agent=agent,
        turns=[
            Turn(
                user=f"Book me a table in {city} tomorrow at 10am.",
                expect=Expect(
                    reply_contains_all=[city],
                    tool_calls_include=["create_booking"],
                ),
            )
        ],
    )
    result.assert_threshold()
