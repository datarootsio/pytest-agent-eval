import pytest

from pytest_agent_eval import AgentReply


@pytest.fixture
def llm_eval_agent():
    async def agent(history):
        return AgentReply("Confirmed! Your reference number: BK-1234, tomorrow at 10am.", [])

    return agent
