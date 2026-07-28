"""Tests for the tool-call presence, ordering and argument evaluators."""

import pytest

from pytest_agent_eval.evaluators.tool_call import ToolCallArgsEvaluator, ToolCallEvaluator
from pytest_agent_eval.models import ToolCall, TurnContext


def _ctx(reply: str = "", tool_calls: list[str] | None = None) -> TurnContext:
    return TurnContext(
        user="test user",
        reply=reply,
        tool_calls=tool_calls or [],
        history=[],
    )


# --- ToolCallEvaluator ---


@pytest.mark.asyncio
async def test_tool_call_must_include_passes():
    ev = ToolCallEvaluator(must_include=["book_slot"])
    result = await ev.evaluate(_ctx(tool_calls=["book_slot", "get_availability"]))
    assert result.passed is True


@pytest.mark.asyncio
async def test_tool_call_must_include_fails_when_missing():
    ev = ToolCallEvaluator(must_include=["book_slot"])
    result = await ev.evaluate(_ctx(tool_calls=["get_availability"]))
    assert result.passed is False
    assert "book_slot" in result.reasoning


@pytest.mark.asyncio
async def test_tool_call_must_exclude_fails_when_present():
    ev = ToolCallEvaluator(must_exclude=["cancel_slot"])
    result = await ev.evaluate(_ctx(tool_calls=["book_slot", "cancel_slot"]))
    assert result.passed is False
    assert "cancel_slot" in result.reasoning


@pytest.mark.asyncio
async def test_tool_call_must_exclude_passes_when_absent():
    ev = ToolCallEvaluator(must_exclude=["cancel_slot"])
    result = await ev.evaluate(_ctx(tool_calls=["book_slot"]))
    assert result.passed is True


@pytest.mark.asyncio
async def test_tool_call_ordered_passes_in_order():
    ev = ToolCallEvaluator(must_include=["a", "b", "c"], ordered=True)
    result = await ev.evaluate(_ctx(tool_calls=["a", "x", "b", "c"]))
    assert result.passed is True


@pytest.mark.asyncio
async def test_tool_call_ordered_fails_out_of_order():
    ev = ToolCallEvaluator(must_include=["a", "b"], ordered=True)
    result = await ev.evaluate(_ctx(tool_calls=["b", "a"]))
    assert result.passed is False


@pytest.mark.asyncio
async def test_tool_call_empty_config_passes():
    ev = ToolCallEvaluator()
    result = await ev.evaluate(_ctx(tool_calls=["anything"]))
    assert result.passed is True


# --- ToolCallArgsEvaluator ---


@pytest.mark.asyncio
async def test_tool_call_args_subset_passes_with_extra_observed_keys():
    ev = ToolCallArgsEvaluator(tool="book_slot", args={"time": "10am"})
    ctx = _ctx(tool_calls=[ToolCall("book_slot", {"time": "10am", "date": "tomorrow"})])
    result = await ev.evaluate(ctx)
    assert result.passed is True


@pytest.mark.asyncio
async def test_tool_call_args_subset_fails_on_wrong_value():
    ev = ToolCallArgsEvaluator(tool="book_slot", args={"time": "11am"})
    ctx = _ctx(tool_calls=[ToolCall("book_slot", {"time": "10am"})])
    result = await ev.evaluate(ctx)
    assert result.passed is False
    assert "11am" in result.reasoning
    assert "10am" in result.reasoning


@pytest.mark.asyncio
async def test_tool_call_args_exact_fails_with_extra_observed_keys():
    ev = ToolCallArgsEvaluator(tool="book_slot", args={"time": "10am"}, mode="exact")
    ctx = _ctx(tool_calls=[ToolCall("book_slot", {"time": "10am", "date": "tomorrow"})])
    result = await ev.evaluate(ctx)
    assert result.passed is False


@pytest.mark.asyncio
async def test_tool_call_args_exact_passes_on_equal_dict():
    ev = ToolCallArgsEvaluator(tool="book_slot", args={"time": "10am"}, mode="exact")
    ctx = _ctx(tool_calls=[ToolCall("book_slot", {"time": "10am"})])
    result = await ev.evaluate(ctx)
    assert result.passed is True


@pytest.mark.asyncio
async def test_tool_call_args_any_matching_call_passes():
    ev = ToolCallArgsEvaluator(tool="book_slot", args={"time": "10am"})
    ctx = _ctx(
        tool_calls=[
            ToolCall("book_slot", {"time": "9am"}),
            ToolCall("book_slot", {"time": "10am"}),
        ]
    )
    result = await ev.evaluate(ctx)
    assert result.passed is True


@pytest.mark.asyncio
async def test_tool_call_args_reports_never_called():
    ev = ToolCallArgsEvaluator(tool="book_slot", args={"time": "10am"})
    result = await ev.evaluate(_ctx(tool_calls=[ToolCall("other_tool", {})]))
    assert result.passed is False
    assert "never called" in result.reasoning


@pytest.mark.asyncio
async def test_tool_call_args_reports_args_not_captured():
    ev = ToolCallArgsEvaluator(tool="book_slot", args={"time": "10am"})
    result = await ev.evaluate(_ctx(tool_calls=["book_slot"]))
    assert result.passed is False
    assert "no dict arguments were captured" in result.reasoning


@pytest.mark.asyncio
async def test_tool_call_args_does_not_crash_on_json_string_args():
    """A ToolCall whose args is an un-parsed JSON string must not raise TypeError."""
    ev = ToolCallArgsEvaluator(tool="book_slot", args={"time": "10am"})
    result = await ev.evaluate(_ctx(tool_calls=[ToolCall("book_slot", '{"time": "10am"}')]))
    assert result.passed is False
    assert "no dict arguments were captured" in result.reasoning


@pytest.mark.asyncio
async def test_tool_call_args_subset_is_top_level_only():
    ev = ToolCallArgsEvaluator(tool="book_slot", args={"opts": {"a": 1}})
    ctx = _ctx(tool_calls=[ToolCall("book_slot", {"opts": {"a": 1, "b": 2}})])
    result = await ev.evaluate(ctx)
    assert result.passed is False


def test_tool_call_args_rejects_unknown_mode():
    with pytest.raises(ValueError, match="subset"):
        ToolCallArgsEvaluator(tool="t", args={}, mode="fuzzy")
