"""N-run evaluation loop with threshold aggregation."""
from __future__ import annotations
import asyncio
from typing import Any, Callable, Awaitable
from pytest_llm_eval.models import (
    Transcript, Turn, Expect, TurnContext, TurnResult, RunResult, TranscriptResult, EvalResult
)
from pytest_llm_eval.evaluators.contains import ContainsEvaluator
from pytest_llm_eval.evaluators.tool_call import ToolCallEvaluator

AgentCallable = Callable[[list[dict[str, Any]]], Awaitable[tuple[str, list[str]]]]


def _build_yaml_evaluators(expect: Expect) -> list[Any]:
    """Convert YAML shorthand fields in Expect to evaluator instances."""
    evaluators = []
    if expect.tool_calls_include or expect.tool_calls_exclude:
        evaluators.append(
            ToolCallEvaluator(
                must_include=expect.tool_calls_include,
                must_exclude=expect.tool_calls_exclude,
            )
        )
    if expect.reply_contains_any or expect.reply_contains_all:
        evaluators.append(
            ContainsEvaluator(
                any_of=expect.reply_contains_any,
                all_of=expect.reply_contains_all,
            )
        )
    return evaluators


async def _run_turn(
    turn: Turn,
    turn_idx: int,
    history: list[dict[str, Any]],
    agent: AgentCallable,
    config_model: str | None = None,
) -> tuple[TurnResult, str, list[str]]:
    """Execute one turn and evaluate results."""
    history.append({"role": "user", "content": turn.user})
    reply, tool_calls = await agent(history)
    history.append({"role": "assistant", "content": reply})

    ctx = TurnContext(
        user=turn.user,
        reply=reply,
        tool_calls=tool_calls,
        history=history[:-2],  # history before this exchange
    )

    evaluators = list(turn.expect.evaluators) + _build_yaml_evaluators(turn.expect)

    if turn.expect.judge is not None:
        from pytest_llm_eval.evaluators.judge import JudgeEvaluator
        judge_model = turn.expect.judge.model or config_model
        evaluators.append(JudgeEvaluator(rubric=turn.expect.judge.rubric, model=judge_model))

    eval_results: list[EvalResult] = []
    for ev in evaluators:
        result = await ev.evaluate(ctx)
        eval_results.append(result)

    turn_passed = all(r.passed for r in eval_results) if eval_results else True
    return TurnResult(turn_index=turn_idx, passed=turn_passed, eval_results=eval_results), reply, tool_calls


async def _run_once(
    transcript: Transcript,
    agent: AgentCallable,
    run_idx: int,
    config_model: str | None = None,
) -> RunResult:
    """Execute all turns once and return a RunResult."""
    history: list[dict[str, Any]] = []
    turn_results: list[TurnResult] = []

    for turn_idx, turn in enumerate(transcript.turns):
        turn_result, _, _ = await _run_turn(turn, turn_idx, history, agent, config_model)
        turn_results.append(turn_result)

    run_passed = all(t.passed for t in turn_results)
    return RunResult(run_index=run_idx, passed=run_passed, turn_results=turn_results)


async def run_transcript(
    transcript: Transcript,
    agent: AgentCallable,
    config_model: str | None = None,
) -> TranscriptResult:
    """Run a transcript N times and aggregate results.

    Args:
        transcript: The transcript to execute.
        agent: Async callable ``(history) -> (reply, tool_calls)``.
        config_model: Fallback model string for JudgeEvaluator (from config).

    Returns:
        TranscriptResult with score, threshold, and per-run details.
    """
    run_results: list[RunResult] = []
    for run_idx in range(transcript.runs):
        run_result = await _run_once(transcript, agent, run_idx, config_model)
        run_results.append(run_result)

    passed_runs = sum(r.passed for r in run_results)
    score = passed_runs / len(run_results)
    passed = score >= transcript.threshold

    return TranscriptResult(
        passed=passed,
        score=score,
        threshold=transcript.threshold,
        runs=run_results,
    )


class EvalSession:
    """Fixture object provided by the llm_eval fixture.

    Args:
        threshold: Pass threshold for this session (overrides config).
        runs: Number of runs (overrides config).
        config_model: Judge model string from config.
        _item: The pytest item node — used by the report plugin to attach score output.
    """

    def __init__(
        self,
        threshold: float,
        runs: int,
        config_model: str | None = None,
        _item: Any = None,
    ) -> None:
        self.threshold = threshold
        self.runs = runs
        self.config_model = config_model
        self._item = _item

    async def run(
        self,
        agent: AgentCallable,
        turns: list[Turn],
    ) -> TranscriptResult:
        """Run a list of turns against the given agent.

        Args:
            agent: Async callable ``(history) -> (reply, tool_calls)``.
            turns: Ordered list of Turn objects.

        Returns:
            TranscriptResult ready for assert_threshold().
        """
        transcript = Transcript(
            id="<python-api>",
            turns=turns,
            threshold=self.threshold,
            runs=self.runs,
        )
        result = await run_transcript(transcript, agent, self.config_model)
        if self._item is not None:
            self._item._eval_result = result
        return result
