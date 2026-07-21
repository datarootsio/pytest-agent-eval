import pytest


@pytest.fixture
def llm_eval_agent():
    async def agent(history):
        return (
            "You're booked! Reference BK-1234.",
            ["authenticate", "fetch_availability", "create_booking"],
        )

    return agent
