from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pytest_agent_eval.evaluators.base import Evaluator
from pytest_agent_eval.evaluators.contains import ContainsEvaluator
from pytest_agent_eval.evaluators.judge import JudgeEvaluator
from pytest_agent_eval.evaluators.tool_call import ToolCallArgsEvaluator, ToolCallEvaluator
from pytest_agent_eval.models import ToolCall, TurnContext


def _ctx(reply: str = "", tool_calls: list[str] | None = None) -> TurnContext:
    return TurnContext(
        user="test user",
        reply=reply,
        tool_calls=tool_calls or [],
        history=[],
    )


# --- ContainsEvaluator ---


@pytest.mark.asyncio
async def test_contains_any_of_passes_when_present():
    ev = ContainsEvaluator(any_of=["confirmed", "booked"])
    result = await ev.evaluate(_ctx(reply="Your booking is confirmed!"))
    assert result.passed is True


@pytest.mark.asyncio
async def test_contains_any_of_fails_when_absent():
    ev = ContainsEvaluator(any_of=["confirmed", "booked"])
    result = await ev.evaluate(_ctx(reply="Something went wrong."))
    assert result.passed is False
    assert "confirmed" in result.reasoning or "booked" in result.reasoning


@pytest.mark.asyncio
async def test_contains_any_of_is_case_insensitive():
    ev = ContainsEvaluator(any_of=["Confirmed"])
    result = await ev.evaluate(_ctx(reply="your booking is CONFIRMED"))
    assert result.passed is True


@pytest.mark.asyncio
async def test_contains_all_of_passes_when_all_present():
    ev = ContainsEvaluator(all_of=["name", "date"])
    result = await ev.evaluate(_ctx(reply="Your name and date are confirmed."))
    assert result.passed is True


@pytest.mark.asyncio
async def test_contains_all_of_fails_when_any_missing():
    ev = ContainsEvaluator(all_of=["name", "date"])
    result = await ev.evaluate(_ctx(reply="Your name is confirmed."))
    assert result.passed is False
    assert "date" in result.reasoning


@pytest.mark.asyncio
async def test_contains_empty_config_always_passes():
    ev = ContainsEvaluator()
    result = await ev.evaluate(_ctx(reply="anything"))
    assert result.passed is True


@pytest.mark.asyncio
async def test_contains_matches_any_passes_on_regex_match():
    ev = ContainsEvaluator(matches_any=[r"ref(erence)? number[:# ]*[A-Z]{2}-\d+"])
    result = await ev.evaluate(_ctx(reply="Your reference number: BK-1234"))
    assert result.passed is True


@pytest.mark.asyncio
async def test_contains_matches_any_fails_when_no_pattern_matches():
    ev = ContainsEvaluator(matches_any=[r"\bBK-\d+\b", r"\bREF-\d+\b"])
    result = await ev.evaluate(_ctx(reply="No reference here."))
    assert result.passed is False
    assert "did not match" in result.reasoning


@pytest.mark.asyncio
async def test_contains_matches_all_passes_when_all_match():
    ev = ContainsEvaluator(matches_all=[r"\d{1,2}(am|pm)", r"tomorrow"])
    result = await ev.evaluate(_ctx(reply="Booked for tomorrow at 10am."))
    assert result.passed is True


@pytest.mark.asyncio
async def test_contains_matches_all_fails_and_names_missing_pattern():
    ev = ContainsEvaluator(matches_all=[r"tomorrow", r"BK-\d+"])
    result = await ev.evaluate(_ctx(reply="Booked for tomorrow."))
    assert result.passed is False
    assert "BK-" in result.reasoning
    assert "tomorrow" not in result.reasoning


@pytest.mark.asyncio
async def test_contains_matches_any_is_case_insensitive_by_default():
    ev = ContainsEvaluator(matches_any=[r"confirmed"])
    result = await ev.evaluate(_ctx(reply="CONFIRMED!"))
    assert result.passed is True


@pytest.mark.asyncio
async def test_contains_case_sensitive_flag_applies_to_regex():
    ev = ContainsEvaluator(matches_any=[r"confirmed"], case_sensitive=True)
    result = await ev.evaluate(_ctx(reply="CONFIRMED!"))
    assert result.passed is False


@pytest.mark.asyncio
async def test_contains_case_sensitive_flag_applies_to_substrings():
    ev = ContainsEvaluator(any_of=["Confirmed"], case_sensitive=True)
    result = await ev.evaluate(_ctx(reply="your booking is CONFIRMED"))
    assert result.passed is False

    ev_all = ContainsEvaluator(all_of=["Booking"], case_sensitive=True)
    result_all = await ev_all.evaluate(_ctx(reply="Booking confirmed"))
    assert result_all.passed is True


def test_contains_invalid_regex_raises_value_error():
    with pytest.raises(ValueError, match="Invalid regex pattern"):
        ContainsEvaluator(matches_any=["[unclosed"])


# --- Evaluator Protocol ---


def test_evaluator_protocol_is_satisfied_by_contains():
    ev = ContainsEvaluator(any_of=["hello"])
    assert isinstance(ev, Evaluator)


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
    assert "no arguments were captured" in result.reasoning


def test_tool_call_args_rejects_unknown_mode():
    with pytest.raises(ValueError, match="subset"):
        ToolCallArgsEvaluator(tool="t", args={}, mode="fuzzy")


@pytest.mark.asyncio
async def test_judge_evaluator_passes_on_positive_verdict():
    mock_output = MagicMock()
    mock_output.passed = True
    mock_output.reasoning = "Reply is helpful and accurate."

    mock_result = MagicMock()
    mock_result.output = mock_output

    with patch("pytest_agent_eval.evaluators.judge.Agent") as MockAgent:
        instance = AsyncMock()
        instance.run = AsyncMock(return_value=mock_result)
        MockAgent.return_value = instance

        ev = JudgeEvaluator(rubric="Be helpful", model="openai:gpt-4o-mini")
        result = await ev.evaluate(_ctx(reply="Here is a helpful response."))

    assert result.passed is True
    assert "helpful" in result.reasoning


@pytest.mark.asyncio
async def test_judge_evaluator_fails_on_negative_verdict():
    mock_output = MagicMock()
    mock_output.passed = False
    mock_output.reasoning = "Reply is off-topic."

    mock_result = MagicMock()
    mock_result.output = mock_output

    with patch("pytest_agent_eval.evaluators.judge.Agent") as MockAgent:
        instance = AsyncMock()
        instance.run = AsyncMock(return_value=mock_result)
        MockAgent.return_value = instance

        ev = JudgeEvaluator(rubric="Be on-topic", model="openai:gpt-4o-mini")
        result = await ev.evaluate(_ctx(reply="Unrelated content."))

    assert result.passed is False
    assert "off-topic" in result.reasoning


@pytest.mark.asyncio
async def test_judge_evaluator_returns_failure_after_retries_exhausted():
    with patch("pytest_agent_eval.evaluators.judge.Agent") as MockAgent:
        instance = AsyncMock()
        instance.run = AsyncMock(side_effect=Exception("API error"))
        MockAgent.return_value = instance

        ev = JudgeEvaluator(rubric="Be helpful", model="openai:gpt-4o-mini", retries=1)
        result = await ev.evaluate(_ctx(reply="hello"))

    assert result.passed is False
    assert "Judge failed" in result.reasoning
    assert instance.run.call_count == 2  # retries=1 means 2 total attempts
