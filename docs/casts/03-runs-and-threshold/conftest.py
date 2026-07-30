import pytest

from pytest_agent_eval import AgentReply

# Run 2 is the flake: no "confirmed", no "booked". Two of three pass, so 0.67 >= 0.66.
REPLIES = [
    "Booking confirmed for tomorrow at 10:00. Reference BK-1042.",
    "Let me pass that on to the scheduling team.",
    "You are booked for tomorrow at 10:00. Reference BK-1044.",
]


@pytest.fixture
def booking_agent():
    # All three runs happen in one process, so an iterator is enough — no counter file.
    replies = iter(REPLIES)

    async def agent(history):
        return AgentReply(next(replies), ["create_booking"])

    return agent
