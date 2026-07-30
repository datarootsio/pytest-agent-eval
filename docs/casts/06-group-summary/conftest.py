import pytest

from pytest_agent_eval import AgentReply


@pytest.fixture
def llm_eval_agent():
    # Deterministic stub: every request is confirmed except the gluten-free tasting
    # menu, which is the one failure the booking gate is there to absorb.
    async def agent(history):
        message = history[-1].content.lower()
        if "gluten-free" in message:
            return AgentReply("I'm not sure I can help with that.", [])
        return AgentReply("Booking confirmed! Reference BK-1234.", ["create_booking"])

    return agent
