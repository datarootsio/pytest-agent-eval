"""Substring and regex evaluator."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from pytest_agent_eval.models import EvalResult, TurnContext


@dataclass(slots=True)
class ContainsEvaluator:
    r"""Check that the reply contains expected substrings or matches regex patterns.

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
        """Validate every pattern at construction time."""
        # Compile and discard: a bad pattern is an authoring error and must fail at
        # construction time, not surface as a per-turn evaluation failure. The compiled
        # objects are not stored, so this stays a plain dataclass with no hidden
        # attributes; re.compile is memoised by the re module cache, so recompiling in
        # evaluate() costs a dict lookup.
        self._compile()

    def _compile(self) -> list[list[re.Pattern[str]]]:
        """Compile both pattern lists, raising a didactic ValueError on a bad pattern."""
        flags = 0 if self.case_sensitive else re.IGNORECASE
        try:
            return [[re.compile(p, flags) for p in patterns] for patterns in (self.matches_any, self.matches_all)]
        except re.error as exc:
            raise ValueError(f"Invalid regex pattern {exc.pattern!r}: {exc}") from exc

    async def evaluate(self, ctx: TurnContext) -> EvalResult:
        """Evaluate substring and regex checks against the reply."""
        # Bound once instead of through a one-line _norm() method: the substring checks
        # compare a folded needle against a folded reply, and this is the only place that
        # decision is made. The regex checks below use re.IGNORECASE on the raw reply
        # instead, so a pattern's own anchors and character classes still mean what they say.
        fold = str if self.case_sensitive else str.lower
        reply = fold(ctx.reply)
        matches_any_compiled, matches_all_compiled = self._compile()

        if self.any_of and not any(fold(s) in reply for s in self.any_of):
            return EvalResult(
                passed=False,
                reasoning=f"Reply did not contain any of {self.any_of!r}",
            )

        missing = [s for s in self.all_of if fold(s) not in reply]
        if missing:
            return EvalResult(
                passed=False,
                reasoning=f"Reply missing required strings: {missing!r}",
            )

        if matches_any_compiled and not any(p.search(ctx.reply) for p in matches_any_compiled):
            return EvalResult(
                passed=False,
                reasoning=f"Reply did not match any of {self.matches_any!r}",
            )

        unmatched = [p.pattern for p in matches_all_compiled if not p.search(ctx.reply)]
        if unmatched:
            return EvalResult(
                passed=False,
                reasoning=f"Reply missing required patterns: {unmatched!r}",
            )

        return EvalResult(passed=True, reasoning="All substring and pattern checks passed")
