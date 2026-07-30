from pytest_agent_eval.models import Message


async def test_naive_booking(agent):
    reply, _ = await agent([Message(role="user", content="book me a slot tomorrow at 10am")])
    assert "confirmed" in reply
