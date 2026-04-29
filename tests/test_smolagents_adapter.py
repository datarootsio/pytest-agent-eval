import types
from typing import Any

from pytest_llm_eval.adapters.smolagents import SmolagentsAdapter


def _make_fake_agent(reply: Any = "ok", new_steps: list[Any] | None = None):
    """Build a duck-typed fake smolagents agent that records `run` calls."""
    fake = types.SimpleNamespace()
    fake.memory = types.SimpleNamespace(steps=[])
    fake.calls: list[tuple[str, bool]] = []

    def run(task: str, reset: bool = True) -> Any:
        fake.calls.append((task, reset))
        if reset:
            fake.memory.steps = []
        for step in new_steps or []:
            fake.memory.steps.append(step)
        return reply

    fake.run = run
    return fake


async def test_first_turn_passes_reset_true():
    fake = _make_fake_agent()
    adapter = SmolagentsAdapter(fake)
    history = [{"role": "user", "content": "hello"}]

    await adapter(history)

    assert fake.calls == [("hello", True)]


async def test_subsequent_turn_passes_reset_false():
    fake = _make_fake_agent()
    adapter = SmolagentsAdapter(fake)
    history = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there"},
        {"role": "user", "content": "follow up"},
    ]

    await adapter(history)

    assert fake.calls == [("follow up", False)]


async def test_returns_reply_string():
    fake = _make_fake_agent(reply=42)
    adapter = SmolagentsAdapter(fake)

    reply, _ = await adapter([{"role": "user", "content": "hi"}])

    assert reply == "42"
