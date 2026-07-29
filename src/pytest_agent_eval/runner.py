"""N-run evaluation loop with threshold aggregation."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest

    from pytest_agent_eval.evaluators.base import Evaluator

from pydantic_ai.models import Model

from pytest_agent_eval.evaluators.contains import ContainsEvaluator
from pytest_agent_eval.evaluators.tool_call import ToolCallEvaluator
from pytest_agent_eval.models import (
    AgentCallable,
    Expect,
    History,
    Message,
    RunResult,
    ToolCall,
    Transcript,
    TranscriptResult,
    Turn,
    TurnContext,
    TurnResult,
)


@dataclass(frozen=True, slots=True)
class JudgeSettings:
    """The judge knobs every evaluator in a transcript shares.

    Args:
        config_model: Fallback model for the judge (from ``[tool.agent_eval] model``).
        judge_model: Dedicated judge model; takes priority over config_model.
        retries: Retry attempts for a failed judge call.
        timeout: Per-judge-call timeout in seconds.
    """

    config_model: str | Model | None = None
    judge_model: str | Model | None = None
    retries: int = 2
    timeout: float = 30.0

    def resolve_model(self, override: str | Model | None = None) -> str | Model | None:
        """Pick the judge model: a per-turn override first, then judge_model, then config_model.

        Args:
            override: Model named on the turn's own judge config, if any.

        Returns:
            The model to hand the judge, or None to let the judge load its own default.
        """
        return override or self.judge_model or self.config_model


_DEFAULT_JUDGE = JudgeSettings()


def _build_yaml_evaluators(expect: Expect) -> list[Evaluator]:
    """Convert YAML shorthand fields in Expect to evaluator instances."""
    evaluators: list[Evaluator] = []
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


class TranscriptRunner:
    """Runs one transcript against one agent under one judge configuration.

    Args:
        agent: Async callable ``(history) -> (reply, tool_calls)``.
        judge: Model, retry and timeout settings for every judge in the transcript.
    """

    def __init__(self, agent: AgentCallable, judge: JudgeSettings) -> None:
        """Bind the agent and the judge settings shared by every turn and run."""
        self.agent = agent
        self.judge = judge

    async def run_turn(self, turn: Turn, index: int, history: History) -> TurnResult:
        """Execute one turn against the agent and evaluate what came back.

        Args:
            turn: The turn to send.
            index: Position of the turn in the transcript.
            history: Conversation so far; the user message and the reply are appended to it.

        Returns:
            TurnResult holding one EvalResult per evaluator.
        """
        history.append(Message(role="user", content=turn.user, audio=None if turn.audio is None else str(turn.audio)))
        reply, raw_tool_calls = await self.agent(history)
        tool_calls = [tc if isinstance(tc, ToolCall) else ToolCall(tc) for tc in raw_tool_calls]
        history.append(Message(role="assistant", content=reply))

        ctx = TurnContext(
            user=turn.user,
            reply=reply,
            tool_calls=tool_calls,
            history=history[:-1],  # history up to but not including the assistant reply
        )

        eval_results = list(await asyncio.gather(*(ev.evaluate(ctx) for ev in self._evaluators(turn.expect))))
        return TurnResult(turn_index=index, passed=all(r.passed for r in eval_results), eval_results=eval_results)

    def _evaluators(self, expect: Expect) -> list[Evaluator]:
        """Collect the turn's explicit evaluators plus the ones its YAML shorthand implies."""
        evaluators = list(expect.evaluators) + _build_yaml_evaluators(expect)

        if expect.judge is not None:
            from pytest_agent_eval.evaluators.judge import JudgeEvaluator

            evaluators.append(
                JudgeEvaluator(
                    rubric=expect.judge.rubric,
                    model=self.judge.resolve_model(expect.judge.model),
                    retries=self.judge.retries,
                    timeout=self.judge.timeout,
                )
            )

        for args_cfg in expect.tool_calls_args:
            if args_cfg.args is not None:
                from pytest_agent_eval.evaluators.tool_call import ToolCallArgsEvaluator

                evaluators.append(ToolCallArgsEvaluator(tool=args_cfg.tool, args=args_cfg.args, mode=args_cfg.mode))
            if args_cfg.judge is not None:
                from pytest_agent_eval.evaluators.judge import ToolCallArgsJudgeEvaluator

                evaluators.append(
                    ToolCallArgsJudgeEvaluator(
                        tool=args_cfg.tool,
                        rubric=args_cfg.judge.rubric,
                        model=self.judge.resolve_model(args_cfg.judge.model),
                        retries=self.judge.retries,
                        timeout=self.judge.timeout,
                    )
                )

        return evaluators

    async def run_once(self, transcript: Transcript, run_index: int) -> RunResult:
        """Execute every turn of the transcript once.

        Args:
            transcript: The transcript to execute.
            run_index: Position of this run among the transcript's runs.

        Returns:
            RunResult that passed only if every turn passed.
        """
        history: History = []
        turn_results: list[TurnResult] = []
        # Sequential, not gathered: each turn is answered against the history the
        # previous turn appended to.
        for index, turn in enumerate(transcript.turns):
            turn_results.append(await self.run_turn(turn, index, history))

        return RunResult(
            run_index=run_index,
            passed=all(t.passed for t in turn_results),
            turn_results=turn_results,
        )

    async def run(self, transcript: Transcript) -> TranscriptResult:
        """Run the transcript ``transcript.runs`` times and aggregate the score.

        Args:
            transcript: The transcript to execute.

        Returns:
            TranscriptResult with score, threshold, and per-run details.
        """
        run_results = list(
            await asyncio.gather(*(self.run_once(transcript, run_index) for run_index in range(transcript.runs)))
        )
        score = sum(r.passed for r in run_results) / len(run_results)

        return TranscriptResult(
            passed=score >= transcript.threshold,
            score=score,
            threshold=transcript.threshold,
            runs=run_results,
        )


async def run_transcript(
    transcript: Transcript,
    agent: AgentCallable,
    judge: JudgeSettings = _DEFAULT_JUDGE,
) -> TranscriptResult:
    """Run a transcript N times and aggregate results.

    Args:
        transcript: The transcript to execute.
        agent: Async callable ``(history) -> (reply, tool_calls)``.
        judge: Model resolution and call limits for any LLM judge in the transcript.

    Returns:
        TranscriptResult with score, threshold, and per-run details.
    """
    return await TranscriptRunner(agent, judge).run(transcript)


class EvalSession:
    """Fixture object provided by the agent_eval fixture.

    Args:
        threshold: Pass threshold for this session (overrides config).
        runs: Number of runs (overrides config).
        judge: Model, retry and timeout settings for the LLM judge.
        _item: The pytest item node — used by the report plugin to attach score output.
    """

    def __init__(
        self,
        threshold: float,
        runs: int,
        *,
        judge: JudgeSettings = _DEFAULT_JUDGE,
        _item: pytest.Item | None = None,
    ) -> None:
        """Initialise an EvalSession with thresholds, run count, and judge settings."""
        self.threshold = threshold
        self.runs = runs
        self.judge = judge
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
        result = await TranscriptRunner(agent, self.judge).run(transcript)
        if self._item is not None:
            self._item._eval_result = result
        return result
