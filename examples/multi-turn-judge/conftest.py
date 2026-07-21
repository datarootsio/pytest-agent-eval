import pytest


@pytest.fixture
def llm_eval_agent():
    # Deterministic mock agent that remembers nothing but answers plausibly per turn.
    async def agent(history):
        message = history[-1]["content"].lower()
        if "11am" in message:
            return "Done — moved your booking from 10am to 11am. Reference stays BK-1234.", ["update_booking"]
        return "Booked for tomorrow at 10am. Reference BK-1234.", ["create_booking"]

    return agent
