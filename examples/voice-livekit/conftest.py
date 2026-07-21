import pytest

from pytest_agent_eval.adapters.livekit import LiveKitAdapter


def make_session():
    # Imported inside the factory so collection works without live credentials.
    from livekit.agents.voice import Agent, AgentSession
    from livekit.plugins import openai

    session = AgentSession(llm=openai.realtime.RealtimeModel())
    agent = Agent(instructions="You are a friendly booking assistant.", tools=[])
    return session, agent


@pytest.fixture
def llm_eval_agent():
    return LiveKitAdapter(make_session)
