"""Substring and regex evaluator."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from pytest_agent_eval.models import EvalResult, TurnContext


@dataclass
class ContainsEvaluator:
    """Check that the reply contains expected substrings or matches regex patterns.

    Args:
        any_of: Reply must contain at least one of these strings.
        all_of: Reply must contain every one of these strings.
        matches_any: Reply must match at least one of these regex patterns (``re.search``).
        matches_all: Reply must match every one of these regex patterns (``re.search``).
        case_sensitive: When False (the default), substring and regex checks ignore case.

    Raises:
        ValueError: If a regex pattern in matches_any/matches_all does not compile.

    Example:
        ```python
        ContainsEvaluator(any_of=["confirmed", "booked"])
        ContainsEvaluator(all_of=["booking", "reference number"])
        ContainsEvaluator(matches_any=[r"ref(erence)? number[:# ]*[A-Z]{2}-\\d+"])
        ContainsEvaluator(all_of=["Booking"], case_sensitive=True)
        ```
    """

    any_of: list[str] = field(default_factory=list)
    all_of: list[str] = field(default_factory=list)
    matches_any: list[str] = field(default_factory=list)
    matches_all: list[str] = field(default_factory=list)
    case_sensitive: bool = False

    def __post_init__(self) -> None:
        # Compile eagerly: a bad pattern is an authoring error and must fail at
        # construction time, not surface as a per-turn evaluation failure.
        flags = 0 if self.case_sensitive else re.IGNORECASE
        try:
            self._matches_any_compiled = [re.compile(p, flags) for p in self.matches_any]
            self._matches_all_compiled = [re.compile(p, flags) for p in self.matches_all]
        except re.error as exc:
            raise ValueError(f"Invalid regex pattern {exc.pattern!r}: {exc}") from exc

    def _norm(self, s: str) -> str:
        return s if self.case_sensitive else s.lower()

    async def evaluate(self, ctx: TurnContext) -> EvalResult:
        """Evaluate substring and regex checks against the reply."""
        reply = self._norm(ctx.reply)

        if self.any_of and not any(self._norm(s) in reply for s in self.any_of):
            return EvalResult(
                passed=False,
                reasoning=f"Reply did not contain any of {self.any_of!r}",
            )

        missing = [s for s in self.all_of if self._norm(s) not in reply]
        if missing:
            return EvalResult(
                passed=False,
                reasoning=f"Reply missing required strings: {missing!r}",
            )

        if self._matches_any_compiled and not any(p.search(ctx.reply) for p in self._matches_any_compiled):
            return EvalResult(
                passed=False,
                reasoning=f"Reply did not match any of {self.matches_any!r}",
            )

        unmatched = [p.pattern for p in self._matches_all_compiled if not p.search(ctx.reply)]
        if unmatched:
            return EvalResult(
                passed=False,
                reasoning=f"Reply missing required patterns: {unmatched!r}",
            )

        return EvalResult(passed=True, reasoning="All substring and pattern checks passed")
