import pytest

from pytest_agent_eval import AgentReply


@pytest.fixture
def booking_agent():
    # The turn is read off the history length: the user message is appended before the
    # agent is called, so turn 1 sees 1 message and turn 2 sees 3.
    async def agent(history):
        if len(history) == 1:
            return AgentReply("Booked you in for 10am tomorrow.", ["create_booking"])
        # The bug: it books a second slot instead of moving the first. Deterministic, so
        # all three runs fail the same way and a retake of the cast is identical.
        return AgentReply("I've moved your booking to 11am.", ["update_booking", "create_booking"])

    return agent
