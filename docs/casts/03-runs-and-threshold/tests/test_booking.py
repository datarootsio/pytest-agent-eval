import pytest

from pytest_agent_eval import Expect, Turn


@pytest.mark.agent_eval(runs=3, threshold=0.66)
async def test_booking_confirmation(agent_eval, booking_agent):
    result = await agent_eval.run(
        agent=booking_agent,
        turns=[
            Turn(
                user="book me a slot tomorrow at 10am",
                expect=Expect(reply_contains_any=["confirmed", "booked"]),
            )
        ],
    )
    result.assert_threshold()
