from __future__ import annotations

import types
from typing import Any

from pytest_agent_eval.adapters.smolagents import SmolagentsAdapter


def _make_fake_agent(reply: Any = "ok", new_steps: list[Any] | None = None) -> types.SimpleNamespace:
    """Build a duck-typed fake smolagents agent that records `run` calls."""
    fake = types.SimpleNamespace()
    fake.memory = types.SimpleNamespace(steps=[])
    fake.calls: list[tuple[str, bool]] = []

    def run(task: str, reset: bool = True) -> Any:
        fake.calls.append((task, reset))
        if reset:
            fake.memory.steps = []
        fake.memory.steps.extend(new_steps or [])
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


def _step(*tool_call_names: str) -> Any:
    """Build a fake step with a `.tool_calls` list of objects exposing `.name`."""
    return types.SimpleNamespace(tool_calls=[types.SimpleNamespace(name=n) for n in tool_call_names])


def _step_no_tool_calls() -> Any:
    """Build a fake step that has no `tool_calls` attribute (e.g. a planning step)."""
    return types.SimpleNamespace()


async def test_extracts_new_tool_calls_only():
    fake = _make_fake_agent(new_steps=[_step("web_search"), _step("create_booking")])
    fake.memory.steps.append(_step("ignored_prior_step"))
    adapter = SmolagentsAdapter(fake)
    history = [
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "ok"},
        {"role": "user", "content": "second"},
    ]

    _, tool_calls = await adapter(history)

    assert tool_calls == ["web_search", "create_booking"]


async def test_handles_steps_without_tool_calls():
    fake = _make_fake_agent(new_steps=[_step_no_tool_calls(), _step("create_booking"), _step_no_tool_calls()])
    adapter = SmolagentsAdapter(fake)

    _, tool_calls = await adapter([{"role": "user", "content": "hi"}])

    assert tool_calls == ["create_booking"]


async def test_filters_python_interpreter_and_final_answer_by_default():
    fake = _make_fake_agent(
        new_steps=[
            _step("python_interpreter"),
            _step("create_booking"),
            _step("final_answer"),
        ]
    )
    adapter = SmolagentsAdapter(fake)

    _, tool_calls = await adapter([{"role": "user", "content": "hi"}])

    assert tool_calls == ["create_booking"]


async def test_include_internal_tools_returns_them():
    fake = _make_fake_agent(
        new_steps=[
            _step("python_interpreter"),
            _step("create_booking"),
            _step("final_answer"),
        ]
    )
    adapter = SmolagentsAdapter(fake, include_internal_tools=True)

    _, tool_calls = await adapter([{"role": "user", "content": "hi"}])

    assert tool_calls == ["python_interpreter", "create_booking", "final_answer"]
