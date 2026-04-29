import pytest
from pytest_llm_eval.models import TurnContext, EvalResult
from pytest_llm_eval.evaluators.base import Evaluator
from pytest_llm_eval.evaluators.contains import ContainsEvaluator
from pytest_llm_eval.evaluators.tool_call import ToolCallEvaluator


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


from unittest.mock import AsyncMock, MagicMock, patch
from pytest_llm_eval.evaluators.judge import JudgeEvaluator


@pytest.mark.asyncio
async def test_judge_evaluator_passes_on_positive_verdict():
    mock_output = MagicMock()
    mock_output.passed = True
    mock_output.reasoning = "Reply is helpful and accurate."

    mock_result = MagicMock()
    mock_result.output = mock_output

    with patch("pytest_llm_eval.evaluators.judge.Agent") as MockAgent:
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

    with patch("pytest_llm_eval.evaluators.judge.Agent") as MockAgent:
        instance = AsyncMock()
        instance.run = AsyncMock(return_value=mock_result)
        MockAgent.return_value = instance

        ev = JudgeEvaluator(rubric="Be on-topic", model="openai:gpt-4o-mini")
        result = await ev.evaluate(_ctx(reply="Unrelated content."))

    assert result.passed is False
    assert "off-topic" in result.reasoning


@pytest.mark.asyncio
async def test_judge_evaluator_returns_failure_after_retries_exhausted():
    with patch("pytest_llm_eval.evaluators.judge.Agent") as MockAgent:
        instance = AsyncMock()
        instance.run = AsyncMock(side_effect=Exception("API error"))
        MockAgent.return_value = instance

        ev = JudgeEvaluator(rubric="Be helpful", model="openai:gpt-4o-mini", retries=1)
        result = await ev.evaluate(_ctx(reply="hello"))

    assert result.passed is False
    assert "Judge failed" in result.reasoning
