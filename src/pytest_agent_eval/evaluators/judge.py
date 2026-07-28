"""LLM judge evaluators using pydantic-ai."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models import Model

from pytest_agent_eval.evaluators._capture import capture_tool_args
from pytest_agent_eval.models import EvalResult, TurnContext

_SYSTEM_PROMPT = (
    "You are a strict rubric evaluator for an LLM agent. "
    "You will receive a rubric, the agent's reply, and the preceding conversation. "
    "Evaluate whether the reply satisfies the rubric."
)

_DEFAULT_CONFIG_PATH = Path("pyproject.toml")

_ARGS_SYSTEM_PROMPT = (
    "You are a strict evaluator of the arguments an LLM agent passed to a tool. "
    "You will receive a rubric, the tool name, and the JSON arguments of every call "
    "to that tool in the turn. Evaluate whether the arguments satisfy the rubric; "
    "pass if ANY call's arguments do."
)


class _JudgeOutput(BaseModel):
    passed: bool
    reasoning: str


def _build_judge_agent(
    model: str | Model | None,
    system_prompt: str,
    config_path: Path = _DEFAULT_CONFIG_PATH,
) -> Agent[None, _JudgeOutput]:
    """Build a judge agent, resolving a None model from [tool.agent_eval].

    config_path is a parameter rather than a hard-coded literal so the fallback is visible
    and testable without chdir. It stays relative by default: this path is only reached
    when an evaluator is constructed directly from the Python API with no model, where the
    working directory is the only thing we know about.
    """
    if model is None:
        # Deferred: importing config at module scope would make models <-> config circular.
        from pytest_agent_eval.config import load_config_from_toml  # noqa: PLC0415

        model = load_config_from_toml(config_path).model
    return Agent(model, output_type=_JudgeOutput, system_prompt=system_prompt)


async def _run_judge(agent: Agent[None, _JudgeOutput], user_msg: str, retries: int, timeout: float) -> EvalResult:
    last_error: Exception | None = None
    for _ in range(retries + 1):
        try:
            result = await asyncio.wait_for(agent.run(user_msg), timeout=timeout)
            output = result.output
            return EvalResult(passed=output.passed, reasoning=output.reasoning)
        except Exception as exc:
            last_error = exc

    return EvalResult(
        passed=False,
        reasoning=f"Judge failed after {retries + 1} attempts: {last_error}",
    )


def _format_judge_prompt(rubric: str, ctx: TurnContext) -> str:
    history_text = "\n".join(f"{m.role.upper()}: {m.content}" for m in ctx.history)
    return (
        f"RUBRIC:\n{rubric}\n\nCONVERSATION HISTORY:\n{history_text}\n\nUSER: {ctx.user}\n\nAGENT REPLY:\n{ctx.reply}"
    )


@dataclass(kw_only=True)
class _JudgeEvaluatorBase:
    """Model resolution and call limits shared by both judge evaluators.

    kw_only so a subclass may declare a field without a default after the defaults here;
    every construction site already uses keywords. Subclasses set ``_system_prompt``.

    Args:
        model: pydantic-ai model string (e.g. ``"openai:gpt-4o"``) or a Model instance.
            Falls back to ``[tool.agent_eval] model`` in pyproject.toml if None.
        retries: Number of retry attempts on API failure before returning a FAIL verdict.
        timeout: Seconds before the judge call times out.
    """

    model: str | Model | None = None
    retries: int = 2
    timeout: float = 30.0

    _system_prompt: ClassVar[str]

    @cached_property
    def _agent(self) -> Agent[None, _JudgeOutput]:
        """The judge agent, built once per instance.

        cached_property rather than a None sentinel plus a _get_agent() accessor, which was
        duplicated verbatim in both subclasses and showed up in dataclasses.fields().
        """
        return _build_judge_agent(self.model, self._system_prompt)

    def _get_agent(self) -> Agent[None, _JudgeOutput]:
        """Return the memoised judge agent."""
        return self._agent


@dataclass(kw_only=True)
class JudgeEvaluator(_JudgeEvaluatorBase):
    """Use an LLM to evaluate the reply against a rubric.

    Uses pydantic-ai under the hood; supports any pydantic-ai compatible model.

    Args:
        rubric: Natural language rubric describing what a passing reply looks like.
        model: pydantic-ai model string (e.g. ``"openai:gpt-4o"``). Falls back to
            ``[tool.agent_eval] model`` in pyproject.toml if None.
        retries: Number of retry attempts on API failure before returning a FAIL verdict.
        timeout: Seconds before the judge call times out.

    Example:
        ```python
        JudgeEvaluator(
            rubric="Reply must confirm booking with date and time",
            model="anthropic:claude-3-5-sonnet-latest",
        )
        ```
    """

    rubric: str

    _system_prompt: ClassVar[str] = _SYSTEM_PROMPT

    async def evaluate(self, ctx: TurnContext) -> EvalResult:
        """Run the LLM judge against the turn and return its verdict."""
        user_msg = _format_judge_prompt(self.rubric, ctx)
        return await _run_judge(self._get_agent(), user_msg, self.retries, self.timeout)


@dataclass(kw_only=True)
class ToolCallArgsJudgeEvaluator(_JudgeEvaluatorBase):
    """Use an LLM to evaluate a tool's call arguments against a rubric.

    Deterministic short-circuits run before any LLM call: if the tool was never
    called, or was called but no arguments were captured, the evaluator fails
    with a precise message and no judge tokens are spent. Otherwise the judge
    receives the tool name and the JSON arguments of every call to it this
    turn, and passes if any call satisfies the rubric.

    Args:
        tool: Name of the tool whose arguments to judge.
        rubric: Natural language rubric describing acceptable arguments.
        model: pydantic-ai model string (e.g. ``"openai:gpt-4o"``). Falls back to
            ``[tool.agent_eval] model`` in pyproject.toml if None.
        retries: Number of retry attempts on API failure before returning a FAIL verdict.
        timeout: Seconds before the judge call times out.

    Example:
        ```python
        ToolCallArgsJudgeEvaluator(
            tool="book_slot",
            rubric="The booking time must be within business hours (9am-5pm).",
        )
        ```
    """

    tool: str
    rubric: str

    _system_prompt: ClassVar[str] = _ARGS_SYSTEM_PROMPT

    async def evaluate(self, ctx: TurnContext) -> EvalResult:
        """Judge the tool's captured arguments, short-circuiting when there is nothing to judge."""
        found = capture_tool_args(self.tool, ctx.tool_calls)
        if found.failure is not None:
            return found.failure
        captured = found.args

        calls_text = "\n\n".join(
            f"CALL {i + 1} ARGUMENTS:\n{json.dumps(args, indent=2, default=str)}" for i, args in enumerate(captured)
        )
        user_msg = f"RUBRIC:\n{self.rubric}\n\nTOOL: {self.tool}\n\n{calls_text}"
        return await _run_judge(self._get_agent(), user_msg, self.retries, self.timeout)
