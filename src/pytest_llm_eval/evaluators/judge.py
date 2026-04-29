"""LLM judge evaluator using pydantic-ai."""
from __future__ import annotations
import asyncio
from dataclasses import dataclass
from pathlib import Path
from pydantic import BaseModel
from pydantic_ai import Agent
from pytest_llm_eval.models import TurnContext, EvalResult

_SYSTEM_PROMPT = (
    "You are a strict rubric evaluator for an LLM agent. "
    "You will receive a rubric, the agent's reply, and the preceding conversation. "
    "Evaluate whether the reply satisfies the rubric."
)


class _JudgeOutput(BaseModel):
    passed: bool
    reasoning: str


def _format_judge_prompt(rubric: str, ctx: TurnContext) -> str:
    history_text = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in ctx.history
    )
    return (
        f"RUBRIC:\n{rubric}\n\n"
        f"CONVERSATION HISTORY:\n{history_text}\n\n"
        f"USER: {ctx.user}\n\n"
        f"AGENT REPLY:\n{ctx.reply}"
    )


@dataclass
class JudgeEvaluator:
    """Use an LLM to evaluate the reply against a rubric.

    Uses pydantic-ai under the hood; supports any pydantic-ai compatible model.

    Args:
        rubric: Natural language rubric describing what a passing reply looks like.
        model: pydantic-ai model string (e.g. ``"openai:gpt-4o"``). Falls back to
            ``[tool.llm_eval] model`` in pyproject.toml if None.
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
    model: str | None = None
    retries: int = 2
    timeout: float = 30.0

    async def evaluate(self, ctx: TurnContext) -> EvalResult:
        from pytest_llm_eval.config import load_config_from_toml
        model_id = self.model if self.model is not None else load_config_from_toml(Path("pyproject.toml")).model
        agent: Agent[None, _JudgeOutput] = Agent(
            model_id,
            output_type=_JudgeOutput,
            system_prompt=_SYSTEM_PROMPT,
        )
        user_msg = _format_judge_prompt(self.rubric, ctx)

        last_error: Exception | None = None
        for _ in range(self.retries + 1):
            try:
                result = await asyncio.wait_for(agent.run(user_msg), timeout=self.timeout)
                output = result.output
                return EvalResult(passed=output.passed, reasoning=output.reasoning)
            except Exception as exc:
                last_error = exc

        return EvalResult(
            passed=False,
            reasoning=f"Judge failed after {self.retries + 1} attempts: {last_error}",
        )
