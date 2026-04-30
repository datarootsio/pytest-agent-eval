"""Evaluator protocol and base result type."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pytest_agent_eval.models import EvalResult, TurnContext


@runtime_checkable
class Evaluator(Protocol):
    """Protocol that all evaluators must satisfy.

    Implement this protocol to create custom evaluators.

    Example:
        ```python
        @dataclass
        class MyEvaluator:
            expected_tone: str

            async def evaluate(self, ctx: TurnContext) -> EvalResult:
                if self.expected_tone in ctx.reply.lower():
                    return EvalResult(passed=True)
                return EvalResult(passed=False, reasoning=f"Expected tone not found")
        ```
    """

    async def evaluate(self, ctx: TurnContext) -> EvalResult:
        """Evaluate a single turn.

        Args:
            ctx: The turn context containing user message, reply, tool calls, and history.

        Returns:
            EvalResult with passed=True/False and optional reasoning.
        """
        ...
