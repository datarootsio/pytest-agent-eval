"""Shared data types for pytest-agent-eval."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


_PathLike = str | Path


@dataclass
class EvalResult:
    """Result from a single evaluator on a single turn."""

    passed: bool
    reasoning: str = ""


class ToolCall(str):
    """A tool-call name that optionally carries the arguments it was invoked with.

    Subclasses ``str`` so name-based checks keep working unchanged: ``"book_slot"
    in ctx.tool_calls``, equality against plain strings, and hand-rolled agents
    returning ``list[str]`` (the runner normalises those to ``ToolCall`` with
    ``args=None``).

    Args:
        name: The tool name.
        args: The arguments the tool was called with, or None when the adapter
            could not capture them.

    Example:
        ```python
        call = ToolCall("book_slot", {"date": "tomorrow", "time": "10am"})
        call == "book_slot"          # True
        call.args["time"]            # "10am"
        ```
    """

    args: dict[str, Any] | None

    def __new__(cls, name: str, args: dict[str, Any] | None = None) -> ToolCall:
        """Create a ToolCall from a tool name and optional captured arguments."""
        obj = super().__new__(cls, name)
        obj.args = args
        return obj

    @property
    def name(self) -> str:
        """The tool name (the string value itself)."""
        return str(self)


@dataclass
class TurnContext:
    """Context passed to every evaluator for a turn.

    Args:
        user: The user message for this turn.
        reply: The agent's reply.
        tool_calls: Tools called during the turn. Each entry is a ToolCall
            (str-compatible); ``.args`` holds captured arguments or None.
        history: Full conversation history in OpenAI message format, up to but not including
            the assistant reply for this turn.
    """

    user: str
    reply: str
    tool_calls: list[ToolCall]
    history: list[dict[str, Any]]


@dataclass
class TurnResult:
    """Aggregated result for a single turn across all evaluators."""

    turn_index: int
    passed: bool
    eval_results: list[EvalResult]


@dataclass
class RunResult:
    """Result of one full run of a transcript (all turns)."""

    run_index: int
    passed: bool
    turn_results: list[TurnResult]


@dataclass
class TranscriptResult:
    """Aggregated result across all runs of a transcript.

    Args:
        passed: True if score >= threshold.
        score: Fraction of runs that passed (0.0-1.0).
        threshold: Required pass fraction.
        runs: Individual run results.
    """

    passed: bool
    score: float
    threshold: float
    runs: list[RunResult]

    @property
    def passed_run_count(self) -> int:
        """Number of runs that passed."""
        return sum(r.passed for r in self.runs)

    def assert_threshold(self) -> None:
        """Raise AssertionError if score is below threshold."""
        if not self.passed:
            raise AssertionError(
                f"LLM eval failed: score={self.score:.2f} < threshold={self.threshold:.2f} "
                f"({self.passed_run_count}/{len(self.runs)} runs passed)"
            )


@dataclass
class JudgeConfig:
    """Judge configuration for a YAML transcript turn.

    Args:
        rubric: The rubric string passed to the LLM judge.
        model: Optional pydantic-ai model ID override (e.g. "openai:gpt-4o").
            Falls back to [tool.agent_eval] model if None.
    """

    rubric: str
    model: str | None = None


@dataclass
class ToolCallArgsConfig:
    """One tool-argument assertion in a YAML transcript turn.

    Args:
        tool: Name of the tool whose arguments to check.
        args: Expected arguments for the deterministic check, or None.
        mode: "subset" or "exact" (deterministic check only).
        judge: Optional LLM-judge config for the arguments.

    Raises:
        ValueError: If neither args nor judge is provided.
    """

    tool: str
    args: dict[str, Any] | None = None
    mode: str = "subset"
    judge: JudgeConfig | None = None

    def __post_init__(self) -> None:
        if self.args is None and self.judge is None:
            raise ValueError(
                f"tool_calls_args entry for {self.tool!r} needs 'args' (deterministic check) "
                "or 'judge' (LLM-judged rubric); got neither"
            )


@dataclass
class Expect:
    """Expectations for a single transcript turn.

    Args:
        evaluators: Programmatic evaluators (Python API).
        judge: YAML-defined judge config.
        tool_calls_include: Tool names that must appear in tool_calls.
        tool_calls_exclude: Tool names that must NOT appear in tool_calls.
        tool_calls_ordered: If True, tool_calls_include must appear in the given order.
        tool_calls_args: Assertions on the arguments of specific tool calls.
        reply_contains_any: Reply must contain at least one of these strings.
        reply_contains_all: Reply must contain all of these strings.
        reply_matches_any: Reply must match at least one of these regex patterns.
        reply_matches_all: Reply must match all of these regex patterns.
    """

    evaluators: list[Any] = field(default_factory=list)
    judge: JudgeConfig | None = None
    tool_calls_include: list[str] = field(default_factory=list)
    tool_calls_exclude: list[str] = field(default_factory=list)
    tool_calls_ordered: bool = False
    tool_calls_args: list[ToolCallArgsConfig] = field(default_factory=list)
    reply_contains_any: list[str] = field(default_factory=list)
    reply_contains_all: list[str] = field(default_factory=list)
    reply_matches_any: list[str] = field(default_factory=list)
    reply_matches_all: list[str] = field(default_factory=list)


@dataclass
class Turn:
    """A single turn in a transcript.

    Args:
        user: The user message (also used as the transcript when ``audio`` is set).
        audio: Optional path to a WAV file for voice adapters. Resolved relative to
            the YAML file's directory when loaded from YAML.
        expect: Expectations for the agent's reply.
    """

    user: str
    audio: _PathLike | None = None
    expect: Expect = field(default_factory=Expect)


@dataclass
class Transcript:
    """A multi-turn evaluation transcript.

    Args:
        id: Unique identifier used as the pytest test name.
        turns: Ordered list of turns.
        threshold: Fraction of runs that must pass (0.0-1.0).
        runs: Number of times to execute this transcript.
        tags: Optional quality-gate tags (e.g. ["gate:booking"]).
    """

    id: str
    turns: list[Turn]
    threshold: float = 0.8
    runs: int = 1
    tags: list[str] = field(default_factory=list)
