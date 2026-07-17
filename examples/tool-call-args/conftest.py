import pytest

from pytest_agent_eval import ToolCall


@pytest.fixture
def llm_eval_agent():
    # Return ToolCall(name, args) instead of plain strings to enable argument assertions.
    async def agent(history):
        call = ToolCall("create_booking", {"time": "10am", "date": "tomorrow", "party_size": 2})
        return "Booked for two, tomorrow at 10am!", [call]

    return agent
