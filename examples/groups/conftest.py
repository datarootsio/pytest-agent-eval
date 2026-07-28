import pytest

from pytest_agent_eval import AgentReply


@pytest.fixture
def llm_eval_agent():
    # Handles the happy path, "fails" on the deliberately hard edge case.
    async def agent(history):
        message = history[-1].content.lower()
        if "gluten-free" in message:
            return AgentReply("I'm not sure I can help with that.", [])
        return AgentReply("Booking confirmed! Reference BK-1234.", ["create_booking"])

    return agent
