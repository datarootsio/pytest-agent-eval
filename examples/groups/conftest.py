import pytest


@pytest.fixture
def llm_eval_agent():
    # Handles the happy path, "fails" on the deliberately hard edge case.
    async def agent(history):
        message = history[-1]["content"].lower()
        if "gluten-free" in message:
            return "I'm not sure I can help with that.", []
        return "Booking confirmed! Reference BK-1234.", ["create_booking"]

    return agent
