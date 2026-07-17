"""N-run evaluation loop with threshold aggregation."""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable

from pytest_agent_eval.evaluators.contains import ContainsEvaluator
from pytest_agent_eval.evaluators.tool_call import ToolCallEvaluator
from pytest_agent_eval.models import (
    Expect,
    RunResult,
    ToolCall,
    Transcript,
    TranscriptResult,
    Turn,
    TurnContext,
    TurnResult,
)

AgentCallable = Callable[[list[dict[str, Any]]], Awaitable[tuple[str, list[str]]]]


def _build_yaml_evaluators(expect: Expect) -> list[Any]:
    """Convert YAML shorthand fields in Expect to evaluator instances."""
    evaluators = []
    if expect.tool_calls_include or expect.tool_calls_exclude:
        evaluators.append(
            ToolCallEvaluator(
                must_include=expect.tool_calls_include,
                must_exclude=expect.tool_calls_exclude,
                ordered=expect.tool_calls_ordered,
            )
        )
    if expect.reply_contains_any or expect.reply_contains_all or expect.reply_matches_any or expect.reply_matches_all:
        evaluators.append(
            ContainsEvaluator(
                any_of=expect.reply_contains_any,
                all_of=expect.reply_contains_all,
                matches_any=expect.reply_matches_any,
                matches_all=expect.reply_matches_all,
            )
        )
    return evaluators


async def _run_turn(
    turn: Turn,
    turn_idx: int,
    history: list[dict[str, Any]],
    agent: AgentCallable,
    config_model: str | None = None,
    judge_model: str | None = None,
) -> tuple[TurnResult, str, list[ToolCall]]:
    """Execute one turn and evaluate results."""
    msg: dict[str, Any] = {"role": "user", "content": turn.user}
    if turn.audio is not None:
        msg["audio"] = str(turn.audio)
    history.append(msg)
    reply, raw_tool_calls = await agent(history)
    tool_calls = [tc if isinstance(tc, ToolCall) else ToolCall(tc) for tc in raw_tool_calls]
    history.append({"role": "assistant", "content": reply})

    ctx = TurnContext(
        user=turn.user,
        reply=reply,
        tool_calls=tool_calls,
        history=history[:-1],  # history up to but not including the assistant reply
    )

    evaluators = list(turn.expect.evaluators) + _build_yaml_evaluators(turn.expect)

    if turn.expect.judge is not None:
        from pytest_agent_eval.evaluators.judge import JudgeEvaluator

        resolved_judge_model = turn.expect.judge.model or judge_model or config_model
        evaluators.append(JudgeEvaluator(rubric=turn.expect.judge.rubric, model=resolved_judge_model))

    eval_results = list(await asyncio.gather(*(ev.evaluate(ctx) for ev in evaluators)))
    turn_passed = all(r.passed for r in eval_results)
    return TurnResult(turn_index=turn_idx, passed=turn_passed, eval_results=eval_results), reply, tool_calls


async def _run_once(
    transcript: Transcript,
    agent: AgentCallable,
    run_idx: int,
    config_model: str | None = None,
    judge_model: str | None = None,
) -> RunResult:
    """Execute all turns once and return a RunResult."""
    history: list[dict[str, Any]] = []
    turn_results: list[TurnResult] = []

    for turn_idx, turn in enumerate(transcript.turns):
        turn_result, _, _ = await _run_turn(turn, turn_idx, history, agent, config_model, judge_model)
        turn_results.append(turn_result)

    run_passed = all(t.passed for t in turn_results)
    return RunResult(run_index=run_idx, passed=run_passed, turn_results=turn_results)


async def run_transcript(
    transcript: Transcript,
    agent: AgentCallable,
    config_model: str | None = None,
    judge_model: str | None = None,
) -> TranscriptResult:
    """Run a transcript N times and aggregate results.

    Args:
        transcript: The transcript to execute.
        agent: Async callable ``(history) -> (reply, tool_calls)``.
        config_model: Fallback model string for JudgeEvaluator (from config).
        judge_model: Dedicated judge model override; takes priority over config_model.

    Returns:
        TranscriptResult with score, threshold, and per-run details.
    """
    run_results = list(
        await asyncio.gather(
            *(_run_once(transcript, agent, run_idx, config_model, judge_model) for run_idx in range(transcript.runs))
        )
    )
    score = sum(r.passed for r in run_results) / len(run_results)
    passed = score >= transcript.threshold

    return TranscriptResult(
        passed=passed,
        score=score,
        threshold=transcript.threshold,
        runs=run_results,
    )


class EvalSession:
    """Fixture object provided by the agent_eval fixture.

    Args:
        threshold: Pass threshold for this session (overrides config).
        runs: Number of runs (overrides config).
        config_model: Default model fallback for JudgeEvaluator.
        judge_model: Dedicated judge model; takes priority over config_model.
        _item: The pytest item node — used by the report plugin to attach score output.
    """

    def __init__(
        self,
        threshold: float,
        runs: int,
        config_model: str | None = None,
        judge_model: str | None = None,
        _item: Any = None,
    ) -> None:
        """Initialise an EvalSession with thresholds, run count, and model fallbacks."""
        self.threshold = threshold
        self.runs = runs
        self.config_model = config_model
        self.judge_model = judge_model
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
        result = await run_transcript(transcript, agent, self.config_model, self.judge_model)
        if self._item is not None:
            self._item._eval_result = result
        return result
