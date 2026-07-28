import pytest

from pytest_agent_eval import AgentReply


@pytest.fixture
def llm_eval_agent():
    async def agent(history):
        return AgentReply(
            "You're booked! Reference BK-1234.",
            ["authenticate", "fetch_availability", "create_booking"],
        )

    return agent
