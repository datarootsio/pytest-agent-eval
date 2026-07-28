"""Tests for the LLM judge evaluators.

Driven through pydantic-ai's own TestModel/FunctionModel rather than
``patch("...judge.Agent")``: the evaluators already accept a model object, so the
real retry loop and structured-output plumbing are exercised instead of mocked over.
"""

import pytest

from pytest_agent_eval.evaluators.judge import JudgeEvaluator, ToolCallArgsJudgeEvaluator, _build_judge_agent
from pytest_agent_eval.models import Message, ToolCall
from tests.helpers.contexts import turn_context
from tests.helpers.judge import FailingJudge, PromptCapturingJudge, verdict_model


@pytest.mark.asyncio
async def test_judge_evaluator_passes_on_positive_verdict() -> None:
    ev = JudgeEvaluator(rubric="Be helpful", model=verdict_model(passed=True, reasoning="Reply is helpful."))
    result = await ev.evaluate(turn_context(reply="Here is a helpful response."))
    assert result.passed is True
    assert "helpful" in result.reasoning


@pytest.mark.asyncio
async def test_judge_evaluator_fails_on_negative_verdict() -> None:
    ev = JudgeEvaluator(rubric="Be on-topic", model=verdict_model(passed=False, reasoning="Reply is off-topic."))
    result = await ev.evaluate(turn_context(reply="Unrelated content."))
    assert result.passed is False
    assert "off-topic" in result.reasoning


@pytest.mark.asyncio
async def test_judge_prompt_carries_the_rubric_reply_and_history() -> None:
    judge = PromptCapturingJudge()
    ev = JudgeEvaluator(rubric="Must confirm the booking", model=judge.model)

    await ev.evaluate(
        turn_context(
            user="book me",
            reply="Confirmed for 10am.",
            history=[Message(role="user", content="earlier turn")],
        )
    )

    assert "Must confirm the booking" in judge.last_prompt
    assert "Confirmed for 10am." in judge.last_prompt
    assert "earlier turn" in judge.last_prompt


@pytest.mark.asyncio
async def test_tool_call_args_judge_passes_verdict_through() -> None:
    judge = PromptCapturingJudge(passed=True, reasoning="Time is within business hours.")
    ev = ToolCallArgsJudgeEvaluator(tool="book_slot", rubric="Business hours only", model=judge.model)

    result = await ev.evaluate(turn_context(tool_calls=[ToolCall("book_slot", {"time": "10am"})]))

    assert result.passed is True
    assert "book_slot" in judge.last_prompt
    assert "10am" in judge.last_prompt
    assert "Business hours only" in judge.last_prompt


@pytest.mark.asyncio
async def test_tool_call_args_judge_sends_every_call_of_the_tool() -> None:
    """The judge passes if ANY call satisfies the rubric, so it must see them all."""
    judge = PromptCapturingJudge()
    ev = ToolCallArgsJudgeEvaluator(tool="book_slot", rubric="r", model=judge.model)

    await ev.evaluate(
        turn_context(
            tool_calls=[
                ToolCall("book_slot", {"time": "3am"}),
                ToolCall("other_tool", {"time": "noon"}),
                ToolCall("book_slot", {"time": "10am"}),
            ]
        )
    )

    assert "3am" in judge.last_prompt
    assert "10am" in judge.last_prompt
    assert "noon" not in judge.last_prompt


@pytest.mark.asyncio
async def test_tool_call_args_judge_short_circuits_when_never_called() -> None:
    """No judge tokens may be spent when there is nothing to judge."""
    judge = PromptCapturingJudge()
    ev = ToolCallArgsJudgeEvaluator(tool="book_slot", rubric="anything", model=judge.model)

    result = await ev.evaluate(turn_context(tool_calls=[]))

    assert result.passed is False
    assert "never called" in result.reasoning
    assert judge.prompts == []


@pytest.mark.asyncio
async def test_tool_call_args_judge_short_circuits_when_args_not_captured() -> None:
    judge = PromptCapturingJudge()
    ev = ToolCallArgsJudgeEvaluator(tool="book_slot", rubric="anything", model=judge.model)

    result = await ev.evaluate(turn_context(tool_calls=["book_slot"]))

    assert result.passed is False
    assert "no dict arguments were captured" in result.reasoning
    assert judge.prompts == []


def test_build_judge_agent_falls_back_to_pyproject_model(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """model=None resolves [tool.agent_eval] model — read from the *current working directory*."""
    (tmp_path / "pyproject.toml").write_text('[tool.agent_eval]\nmodel = "test"\n')
    monkeypatch.chdir(tmp_path)

    agent = _build_judge_agent(None, "system prompt")

    assert agent.model is not None
    assert "test" in repr(agent.model).lower()


def test_build_judge_agent_uses_a_model_object_verbatim() -> None:
    """A model instance must be passed through, not stringified — the SDK contract path."""
    model = verdict_model(passed=True, reasoning="x")
    assert _build_judge_agent(model, "system prompt").model is model


@pytest.mark.asyncio
async def test_judge_evaluator_returns_failure_after_retries_exhausted() -> None:
    judge = FailingJudge(error="API error")
    ev = JudgeEvaluator(rubric="Be helpful", model=judge.model, retries=1)

    result = await ev.evaluate(turn_context(reply="hello"))

    assert result.passed is False
    assert "Judge failed after 2 attempts" in result.reasoning
    assert "API error" in result.reasoning
    assert judge.attempts == 2  # retries=1 means 2 total attempts


@pytest.mark.asyncio
async def test_judge_evaluator_recovers_on_a_later_attempt() -> None:
    """A transient failure must not be reported as a verdict."""
    judge = FailingJudge(error="transient", fail_times=1)
    ev = JudgeEvaluator(rubric="Be helpful", model=judge.model, retries=2)

    result = await ev.evaluate(turn_context(reply="hello"))

    assert result.passed is True
    assert result.reasoning == "recovered"
    assert judge.attempts == 2


def test_judge_evaluators_build_their_agent_once() -> None:
    """The agent is memoised per instance; rebuilding it per turn would re-resolve the model."""
    judge = JudgeEvaluator(rubric="r", model="test")
    assert judge._get_agent() is judge._get_agent()

    args_judge = ToolCallArgsJudgeEvaluator(tool="t", rubric="r", model="test")
    assert args_judge._get_agent() is args_judge._get_agent()


def test_judge_agent_is_not_a_dataclass_field() -> None:
    """The memoised agent must not show up in fields() or repr().

    It was previously a field(default=None, init=False, repr=False) — a workaround for
    storing it at all. cached_property removes the need for the workaround.
    """
    import dataclasses

    judge = JudgeEvaluator(rubric="r", model="test")
    assert "_agent" not in {f.name for f in dataclasses.fields(judge)}
    assert "_agent" not in repr(judge)
    assert "rubric" in repr(judge)


def test_build_judge_agent_config_path_is_explicit(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The [tool.agent_eval] fallback takes the path as a parameter, not a hidden CWD read."""
    (tmp_path / "elsewhere.toml").write_text('[tool.agent_eval]\nmodel = "test"\n')
    # Somewhere with no pyproject.toml at all, so only the explicit path can satisfy this.
    monkeypatch.chdir(tmp_path)

    agent = _build_judge_agent(None, "system prompt", tmp_path / "elsewhere.toml")

    assert "test" in repr(agent.model).lower()
