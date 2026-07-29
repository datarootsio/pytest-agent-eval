import pytest

from pytest_agent_eval import AgentReply


@pytest.fixture
def llm_eval_agent():
    # Deterministic mock agent; replace with a framework adapter to test yours.
    async def agent(history):
        return AgentReply("Booking confirmed! Reference BK-1234.", ["create_booking"])

    return agent
