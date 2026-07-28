"""Tool call assertion evaluators."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from pytest_agent_eval.models import EvalResult, JsonMapping, ToolCallArgsMode, TurnContext

if TYPE_CHECKING:
    from collections.abc import Sequence


def _is_ordered_subsequence(needle: Sequence[str], haystack: Sequence[str]) -> bool:
    it = iter(haystack)
    return all(n in it for n in needle)


@dataclass
class ToolCallEvaluator:
    """Validate that specific tools were (or were not) called.

    Args:
        must_include: Tool names that must appear in tool_calls.
        must_exclude: Tool names that must NOT appear in tool_calls.
        ordered: If True, must_include tools must appear in the given order.

    Example:
        ```python
        ToolCallEvaluator(must_include=["book_slot"], must_exclude=["cancel_slot"])
        ToolCallEvaluator(must_include=["auth", "fetch", "respond"], ordered=True)
        ```
    """

    must_include: list[str] = field(default_factory=list)
    must_exclude: list[str] = field(default_factory=list)
    ordered: bool = False

    async def evaluate(self, ctx: TurnContext) -> EvalResult:
        """Evaluate tool call presence and ordering."""
        failures: list[str] = []
        if not self.ordered:
            failures += [
                f"Expected tool {tool!r} not in {ctx.tool_calls!r}"
                for tool in self.must_include
                if tool not in ctx.tool_calls
            ]
        failures += [f"Forbidden tool {tool!r} was called" for tool in self.must_exclude if tool in ctx.tool_calls]
        if self.ordered and self.must_include and not _is_ordered_subsequence(self.must_include, ctx.tool_calls):
            failures.append(f"Tools {self.must_include!r} not called in order in {ctx.tool_calls!r}")

        if failures:
            return EvalResult(passed=False, reasoning="\n".join(failures))
        return EvalResult(passed=True, reasoning="All tool call checks passed")


@dataclass
class ToolCallArgsEvaluator:
    """Assert the arguments a tool was called with.

    When the tool was called more than once in a turn, the check passes if ANY
    of those calls matches the expected arguments.

    Args:
        tool: Name of the tool to check.
        args: Expected arguments.
        mode: ``"subset"`` (every expected top-level key/value must appear in the
            observed args; extra observed keys are fine, but nested values are
            compared exactly) or ``"exact"`` (observed args must equal the
            expected dict exactly).

    Example:
        ```python
        ToolCallArgsEvaluator(tool="book_slot", args={"time": "10am"})
        ToolCallArgsEvaluator(tool="book_slot", args={"time": "10am", "date": "tomorrow"}, mode="exact")
        ```
    """

    tool: str
    args: JsonMapping
    mode: ToolCallArgsMode = "subset"

    def __post_init__(self) -> None:
        """Reject an unknown comparison mode at construction time."""
        if self.mode not in ("subset", "exact"):
            raise ValueError(f"ToolCallArgsEvaluator mode must be 'subset' or 'exact', got {self.mode!r}")

    def _matches(self, observed: JsonMapping) -> bool:
        if self.mode == "exact":
            return observed == self.args
        return all(k in observed and observed[k] == v for k, v in self.args.items())

    async def evaluate(self, ctx: TurnContext) -> EvalResult:
        """Evaluate the expected arguments against every call of the tool this turn."""
        matching = [tc for tc in ctx.tool_calls if tc == self.tool]
        if not matching:
            return EvalResult(
                passed=False,
                reasoning=f"Tool {self.tool!r} was never called (tools called: {[str(tc) for tc in ctx.tool_calls]!r})",
            )

        # Walrus, not getattr-then-isinstance: the latter narrows the *expression*, so
        # tc.args stayed JsonMapping | None and the None leaked into the comparison.
        captured = [args for tc in matching if isinstance(args := getattr(tc, "args", None), dict)]
        if not captured:
            return EvalResult(
                passed=False,
                reasoning=(
                    f"Tool {self.tool!r} was called but no dict arguments were captured. "
                    "Argument assertions need the agent/adapter to return ToolCall(name, args) "
                    "with args as a mapping (a JSON string is not enough — parse it first)."
                ),
            )

        if any(self._matches(observed) for observed in captured):
            return EvalResult(passed=True, reasoning=f"Tool {self.tool!r} called with expected args ({self.mode})")

        return EvalResult(
            passed=False,
            reasoning=(
                f"Tool {self.tool!r} argument mismatch ({self.mode} mode): "
                f"expected {self.args!r}, observed {captured!r}"
            ),
        )
