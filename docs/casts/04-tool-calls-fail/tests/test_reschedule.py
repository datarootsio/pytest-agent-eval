# tests/test_reschedule.py

import pytest

from pytest_agent_eval import Expect, Turn


@pytest.mark.agent_eval(runs=3, threshold=0.8)
async def test_reschedule_flow(agent_eval, booking_agent):
    result = await agent_eval.run(
        agent=booking_agent,
        turns=[
            Turn(
                user="Book me a slot tomorrow at 10am.",
                expect=Expect(tool_calls_include=["create_booking"]),
            ),
            Turn(
                user="Actually make it 11am.",
                expect=Expect(
                    tool_calls_include=["update_booking"],
                    tool_calls_exclude=["create_booking"],
                ),
            ),
        ],
    )
    result.assert_threshold()
