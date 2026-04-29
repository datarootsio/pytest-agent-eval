"""Substring-based evaluator."""
from __future__ import annotations
from dataclasses import dataclass, field
from pytest_llm_eval.models import TurnContext, EvalResult


@dataclass
class ContainsEvaluator:
    """Check that the reply contains expected substrings.

    Args:
        any_of: Reply must contain at least one of these strings (case-insensitive).
        all_of: Reply must contain every one of these strings (case-insensitive).

    Example:
        ```python
        ContainsEvaluator(any_of=["confirmed", "booked"])
        ContainsEvaluator(all_of=["booking", "reference number"])
        ```
    """
    any_of: list[str] = field(default_factory=list)
    all_of: list[str] = field(default_factory=list)

    async def evaluate(self, ctx: TurnContext) -> EvalResult:
        """Evaluate substring presence in the reply."""
        lowered = ctx.reply.lower()

        if self.any_of and not any(s.lower() in lowered for s in self.any_of):
            return EvalResult(
                passed=False,
                reasoning=f"Reply did not contain any of {self.any_of!r}",
            )

        missing = [s for s in self.all_of if s.lower() not in lowered]
        if missing:
            return EvalResult(
                passed=False,
                reasoning=f"Reply missing required strings: {missing!r}",
            )

        return EvalResult(passed=True, reasoning="All substring checks passed")
