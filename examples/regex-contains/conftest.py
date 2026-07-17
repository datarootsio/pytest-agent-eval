import pytest


@pytest.fixture
def llm_eval_agent():
    async def agent(history):
        return "Confirmed! Your reference number: BK-1234, tomorrow at 10am.", []

    return agent
