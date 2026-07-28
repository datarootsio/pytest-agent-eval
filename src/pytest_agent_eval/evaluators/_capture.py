"""Shared tool-argument capture for the deterministic and LLM-judged argument evaluators.

Both evaluators need the same two short-circuits before they can assert anything: the tool
may never have been called, or it may have been called by an adapter that could not capture
its arguments. Those are different failures with different fixes, and the messages telling
them apart were duplicated verbatim in two files.
"""

from __future__ import annotations

from dataclasses import dataclass

from pytest_agent_eval.models import EvalResult, JsonMapping, ToolCalls


@dataclass(frozen=True, slots=True)
class CapturedArgs:
    """The arguments a tool was called with, or the reason there are none to check.

    Callers branch on ``failure``: when it is not None it is the verdict to return, without
    spending a judge call. Narrowing on the field directly is what lets the type checker
    see that ``args`` is populated on the other branch.

    Args:
        args: One entry per call of the tool whose arguments were captured as a mapping.
        failure: A ready-made failing EvalResult, or None when capture succeeded.
    """

    args: tuple[JsonMapping, ...] = ()
    failure: EvalResult | None = None


def capture_tool_args(tool: str, tool_calls: ToolCalls) -> CapturedArgs:
    """Collect the captured arguments of every call to ``tool`` this turn.

    Args:
        tool: Name of the tool whose arguments to collect.
        tool_calls: The turn's tool calls.

    Returns:
        CapturedArgs holding either the arguments or the failure explaining their absence.
    """
    matching = [tc for tc in tool_calls if tc == tool]
    if not matching:
        return CapturedArgs(
            failure=EvalResult(
                passed=False,
                reasoning=f"Tool {tool!r} was never called (tools called: {[str(tc) for tc in tool_calls]!r})",
            )
        )

    # Walrus, not getattr-then-isinstance: the latter narrows the *expression*, so tc.args
    # stays JsonMapping | None and the None leaks into the comparison.
    captured = tuple(args for tc in matching if isinstance(args := getattr(tc, "args", None), dict))
    if not captured:
        return CapturedArgs(
            failure=EvalResult(
                passed=False,
                reasoning=(
                    f"Tool {tool!r} was called but no dict arguments were captured. "
                    "Argument assertions need the agent/adapter to return ToolCall(name, args) "
                    "with args as a mapping (a JSON string is not enough — parse it first)."
                ),
            )
        )
    return CapturedArgs(args=captured)
