import pytest

from pytest_agent_eval import AgentReply


@pytest.fixture
def llm_eval_agent():
    # --collect-only never calls this. It is here because the page's claim is that the
    # transcript is a real pytest test, and a real one runs: `pytest --agent-eval-live`
    # in this directory passes.
    async def agent(history):
        return AgentReply("Moved to 11am. Reference BK-1234.", ["update_booking"])

    return agent
