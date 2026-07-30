# tests/test_reschedule.py

import pytest

from pytest_agent_eval import Expect, JudgeEvaluator, Turn

RESCHEDULE_RUBRIC = """
The reply must:
  - state the new time explicitly
  - repeat the existing booking reference, unchanged
The reply must not:
  - invent or alter a reference number
  - ask the user to repeat information they have already given
"""


@pytest.mark.agent_eval(runs=3, threshold=0.66)
async def test_reschedule_reads_well(agent_eval, booking_agent):
    result = await agent_eval.run(
        agent=booking_agent,
        turns=[
            Turn(user="Book me a slot tomorrow at 10am."),
            Turn(
                user="Actually make it 11am.",
                expect=Expect(
                    tool_calls_include=["update_booking"],
                    evaluators=[JudgeEvaluator(rubric=RESCHEDULE_RUBRIC)],
                ),
            ),
        ],
    )
    result.assert_threshold()
