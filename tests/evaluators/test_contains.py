"""Tests for the substring and regex evaluator, plus the Evaluator protocol itself."""

import pytest

from pytest_agent_eval.evaluators.base import Evaluator
from pytest_agent_eval.evaluators.contains import ContainsEvaluator
from tests.helpers.contexts import turn_context


# --- ContainsEvaluator ---


@pytest.mark.asyncio
async def test_contains_any_of_passes_when_present():
    ev = ContainsEvaluator(any_of=["confirmed", "booked"])
    result = await ev.evaluate(turn_context(reply="Your booking is confirmed!"))
    assert result.passed is True


@pytest.mark.asyncio
async def test_contains_any_of_fails_when_absent():
    ev = ContainsEvaluator(any_of=["confirmed", "booked"])
    result = await ev.evaluate(turn_context(reply="Something went wrong."))
    assert result.passed is False
    assert "confirmed" in result.reasoning or "booked" in result.reasoning


@pytest.mark.asyncio
async def test_contains_any_of_is_case_insensitive():
    ev = ContainsEvaluator(any_of=["Confirmed"])
    result = await ev.evaluate(turn_context(reply="your booking is CONFIRMED"))
    assert result.passed is True


@pytest.mark.asyncio
async def test_contains_all_of_passes_when_all_present():
    ev = ContainsEvaluator(all_of=["name", "date"])
    result = await ev.evaluate(turn_context(reply="Your name and date are confirmed."))
    assert result.passed is True


@pytest.mark.asyncio
async def test_contains_all_of_fails_when_any_missing():
    ev = ContainsEvaluator(all_of=["name", "date"])
    result = await ev.evaluate(turn_context(reply="Your name is confirmed."))
    assert result.passed is False
    assert "date" in result.reasoning


@pytest.mark.asyncio
async def test_contains_empty_config_always_passes():
    ev = ContainsEvaluator()
    result = await ev.evaluate(turn_context(reply="anything"))
    assert result.passed is True


@pytest.mark.asyncio
async def test_contains_matches_any_passes_on_regex_match():
    ev = ContainsEvaluator(matches_any=[r"ref(erence)? number[:# ]*[A-Z]{2}-\d+"])
    result = await ev.evaluate(turn_context(reply="Your reference number: BK-1234"))
    assert result.passed is True


@pytest.mark.asyncio
async def test_contains_matches_any_fails_when_no_pattern_matches():
    ev = ContainsEvaluator(matches_any=[r"\bBK-\d+\b", r"\bREF-\d+\b"])
    result = await ev.evaluate(turn_context(reply="No reference here."))
    assert result.passed is False
    assert "did not match" in result.reasoning


@pytest.mark.asyncio
async def test_contains_matches_all_passes_when_all_match():
    ev = ContainsEvaluator(matches_all=[r"\d{1,2}(am|pm)", r"tomorrow"])
    result = await ev.evaluate(turn_context(reply="Booked for tomorrow at 10am."))
    assert result.passed is True


@pytest.mark.asyncio
async def test_contains_matches_all_fails_and_names_missing_pattern():
    ev = ContainsEvaluator(matches_all=[r"tomorrow", r"BK-\d+"])
    result = await ev.evaluate(turn_context(reply="Booked for tomorrow."))
    assert result.passed is False
    assert "BK-" in result.reasoning
    assert "tomorrow" not in result.reasoning


@pytest.mark.asyncio
async def test_contains_matches_any_is_case_insensitive_by_default():
    ev = ContainsEvaluator(matches_any=[r"confirmed"])
    result = await ev.evaluate(turn_context(reply="CONFIRMED!"))
    assert result.passed is True


@pytest.mark.asyncio
async def test_contains_case_sensitive_flag_applies_to_regex():
    ev = ContainsEvaluator(matches_any=[r"confirmed"], case_sensitive=True)
    result = await ev.evaluate(turn_context(reply="CONFIRMED!"))
    assert result.passed is False


@pytest.mark.asyncio
async def test_contains_case_sensitive_flag_applies_to_substrings():
    ev = ContainsEvaluator(any_of=["Confirmed"], case_sensitive=True)
    result = await ev.evaluate(turn_context(reply="your booking is CONFIRMED"))
    assert result.passed is False

    ev_all = ContainsEvaluator(all_of=["Booking"], case_sensitive=True)
    result_all = await ev_all.evaluate(turn_context(reply="Booking confirmed"))
    assert result_all.passed is True


def test_contains_invalid_regex_raises_value_error():
    with pytest.raises(ValueError, match="Invalid regex pattern"):
        ContainsEvaluator(matches_any=["[unclosed"])


# --- Evaluator Protocol ---


def test_evaluator_protocol_is_satisfied_by_contains():
    ev = ContainsEvaluator(any_of=["hello"])
    assert isinstance(ev, Evaluator)
