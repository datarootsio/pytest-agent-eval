import pytest

from pytest_agent_eval.adapters.livekit import LiveKitAdapter


def make_session():
    # Imported inside the factory, not at module scope, so `--collect-only` works with
    # no livekit extra and no credentials: nothing is built until a turn actually runs.
    from livekit.agents.voice import Agent, AgentSession
    from livekit.plugins import openai

    session = AgentSession(llm=openai.realtime.RealtimeModel())
    agent = Agent(
        instructions="You are a booking assistant. Confirm each request and repeat the time back.",
        tools=[],
    )
    return session, agent


@pytest.fixture
def llm_eval_agent():
    # One fresh session per turn; the adapter streams that turn's WAV into it.
    return LiveKitAdapter(make_session)
