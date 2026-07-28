"""Tests for the LLM judge evaluators."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pytest_agent_eval.evaluators.judge import JudgeEvaluator
from pytest_agent_eval.models import ToolCall, TurnContext


def _ctx(reply: str = "", tool_calls: list[str] | None = None) -> TurnContext:
    return TurnContext(
        user="test user",
        reply=reply,
        tool_calls=tool_calls or [],
        history=[],
    )


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
async def test_tool_call_args_judge_passes_verdict_through():
    from pytest_agent_eval.evaluators.judge import ToolCallArgsJudgeEvaluator

    mock_output = MagicMock()
    mock_output.passed = True
    mock_output.reasoning = "Time is within business hours."
    mock_result = MagicMock()
    mock_result.output = mock_output

    with patch("pytest_agent_eval.evaluators.judge.Agent") as MockAgent:
        instance = AsyncMock()
        instance.run = AsyncMock(return_value=mock_result)
        MockAgent.return_value = instance

        ev = ToolCallArgsJudgeEvaluator(tool="book_slot", rubric="Business hours only", model="openai:gpt-4o-mini")
        result = await ev.evaluate(_ctx(tool_calls=[ToolCall("book_slot", {"time": "10am"})]))

    assert result.passed is True
    prompt = instance.run.call_args.args[0]
    assert "book_slot" in prompt
    assert "10am" in prompt
    assert "Business hours only" in prompt


@pytest.mark.asyncio
async def test_tool_call_args_judge_short_circuits_when_never_called():
    from pytest_agent_eval.evaluators.judge import ToolCallArgsJudgeEvaluator

    with patch("pytest_agent_eval.evaluators.judge.Agent") as MockAgent:
        ev = ToolCallArgsJudgeEvaluator(tool="book_slot", rubric="anything", model="openai:gpt-4o-mini")
        result = await ev.evaluate(_ctx(tool_calls=[]))

    assert result.passed is False
    assert "never called" in result.reasoning
    MockAgent.assert_not_called()


@pytest.mark.asyncio
async def test_tool_call_args_judge_short_circuits_when_args_not_captured():
    from pytest_agent_eval.evaluators.judge import ToolCallArgsJudgeEvaluator

    with patch("pytest_agent_eval.evaluators.judge.Agent") as MockAgent:
        ev = ToolCallArgsJudgeEvaluator(tool="book_slot", rubric="anything", model="openai:gpt-4o-mini")
        result = await ev.evaluate(_ctx(tool_calls=["book_slot"]))

    assert result.passed is False
    assert "no dict arguments were captured" in result.reasoning
    MockAgent.assert_not_called()


def test_build_judge_agent_falls_back_to_pyproject_model(tmp_path, monkeypatch: pytest.MonkeyPatch):
    """model=None resolves [tool.agent_eval] model — read from the *current working directory*."""
    from pytest_agent_eval.evaluators.judge import _build_judge_agent

    (tmp_path / "pyproject.toml").write_text('[tool.agent_eval]\nmodel = "test"\n')
    monkeypatch.chdir(tmp_path)

    agent = _build_judge_agent(None, "system prompt")

    assert agent.model is not None
    assert "test" in repr(agent.model).lower()


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


def test_judge_evaluators_build_their_agent_once():
    """The agent is memoised per instance; rebuilding it per turn would re-resolve the model."""
    from pytest_agent_eval.evaluators.judge import JudgeEvaluator, ToolCallArgsJudgeEvaluator

    judge = JudgeEvaluator(rubric="r", model="test")
    assert judge._get_agent() is judge._get_agent()

    args_judge = ToolCallArgsJudgeEvaluator(tool="t", rubric="r", model="test")
    assert args_judge._get_agent() is args_judge._get_agent()
