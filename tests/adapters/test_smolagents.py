from __future__ import annotations

import types
from typing import Any

from pytest_agent_eval.adapters.smolagents import SmolagentsAdapter
from tests.helpers.smolagents_fakes import FakeSmolagent, FakeStep, FakeToolCall, RunCall


def _make_fake_agent(reply: Any = "ok", new_steps: list[Any] | None = None) -> FakeSmolagent:
    return FakeSmolagent(reply=reply, new_steps=new_steps)


async def test_first_turn_passes_reset_true():
    fake = _make_fake_agent()
    adapter = SmolagentsAdapter(fake)
    history = [{"role": "user", "content": "hello"}]

    await adapter(history)

    assert fake.calls == [RunCall(task="hello", reset=True)]


async def test_subsequent_turn_passes_reset_false():
    fake = _make_fake_agent()
    adapter = SmolagentsAdapter(fake)
    history = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there"},
        {"role": "user", "content": "follow up"},
    ]

    await adapter(history)

    assert fake.calls == [RunCall(task="follow up", reset=False)]


async def test_returns_reply_string():
    fake = _make_fake_agent(reply=42)
    adapter = SmolagentsAdapter(fake)

    reply, _ = await adapter([{"role": "user", "content": "hi"}])

    assert reply == "42"


def _step(*tool_call_names: str) -> FakeStep:
    return FakeStep(tool_calls=[FakeToolCall(name=n) for n in tool_call_names])


def _planning_step() -> Any:
    # SimpleNamespace on purpose: the tool_calls attribute must be *absent*, which is
    # what exercises the adapter's getattr(step, "tool_calls", None) default.
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
    fake = _make_fake_agent(new_steps=[_planning_step(), _step("create_booking"), _planning_step()])
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


async def test_captures_tool_call_arguments():
    step = FakeStep(tool_calls=[FakeToolCall(name="create_booking", arguments={"time": "10am"})])
    fake = _make_fake_agent(new_steps=[step])
    adapter = SmolagentsAdapter(fake)

    _, tool_calls = await adapter([{"role": "user", "content": "hi"}])

    assert tool_calls == ["create_booking"]
    assert tool_calls[0].args == {"time": "10am"}


async def test_tool_call_without_arguments_degrades_to_none():
    fake = _make_fake_agent(new_steps=[_step("create_booking")])
    adapter = SmolagentsAdapter(fake)

    _, tool_calls = await adapter([{"role": "user", "content": "hi"}])

    assert tool_calls[0].args is None


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
