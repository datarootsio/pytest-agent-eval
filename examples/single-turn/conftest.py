import pytest


@pytest.fixture
def llm_eval_agent():
    # Deterministic mock agent; replace with a framework adapter to test yours.
    async def agent(history):
        return "Booking confirmed! Reference BK-1234.", ["create_booking"]

    return agent
