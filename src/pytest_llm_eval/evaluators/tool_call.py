"""Tool call assertion evaluator."""
from __future__ import annotations
from dataclasses import dataclass, field
from pytest_llm_eval.models import TurnContext, EvalResult


def _is_ordered_subsequence(needle: list[str], haystack: list[str]) -> bool:
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

        for tool in self.must_include:
            if tool not in ctx.tool_calls:
                failures.append(f"Expected tool {tool!r} not in {ctx.tool_calls!r}")

        for tool in self.must_exclude:
            if tool in ctx.tool_calls:
                failures.append(f"Forbidden tool {tool!r} was called")

        if self.ordered and self.must_include:
            if not _is_ordered_subsequence(self.must_include, ctx.tool_calls):
                failures.append(
                    f"Tools {self.must_include!r} not called in order in {ctx.tool_calls!r}"
                )

        if failures:
            return EvalResult(passed=False, reasoning="\n".join(failures))
        return EvalResult(passed=True, reasoning="All tool call checks passed")
