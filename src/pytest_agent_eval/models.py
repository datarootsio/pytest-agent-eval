"""Shared data types and type aliases for pytest-agent-eval.

Structural types are spelled once here and referred to by name everywhere else, so a
change to the agent contract is a one-line edit rather than a sweep.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal, NamedTuple, Protocol, TypeAlias, runtime_checkable

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    WithJsonSchema,
    field_validator,
    model_validator,
)
from pydantic.json_schema import SkipJsonSchema
from pydantic_ai.models import Model

_PathLike = str | Path

Role: TypeAlias = Literal["user", "assistant", "system"]
"""Who produced a conversation message."""

JsonMapping: TypeAlias = dict[str, JsonValue]
"""A JSON object — tool-call arguments, serialised results, config sections.

``JsonValue`` is re-exported from pydantic rather than hand-rolled: a recursive alias
written as a string cannot be resolved by pydantic when it appears in a model field.
"""

ToolArgs: TypeAlias = dict[str, object]
"""The arguments an adapter captured off one tool call.

``object`` values rather than ``JsonValue``, because that is the truth: LangChain declares
its tool-call arguments as an untyped dict, and pydantic-ai's ``args_as_dict()`` returns
whatever the model emitted, so a value outside JSON reaches us routinely — which is exactly
why the judge serialises these with ``json.dumps(..., default=str)``. Saying so lets the
adapters *construct* this type from a raw mapping instead of asserting it with a cast.

``JsonMapping`` stays for data that genuinely is JSON: YAML, TOML, the xdist wire, and
``ToolCallArgsConfig.args`` (which a transcript author writes by hand).
"""

ToolCalls: TypeAlias = Sequence[str]
"""Tool calls from one turn.

``Sequence``, not ``list``: ``list`` is invariant, so ``list[ToolCall]`` is not
assignable to ``list[str]`` even though ``ToolCall`` subclasses ``str``. Every adapter
and the tool-call evaluator hit that, and widening to ``Sequence`` fixes all of them at
once while letting a ``ToolCall`` flow through the contract without a cast.
"""

ToolCallArgsMode: TypeAlias = Literal["subset", "exact"]
"""How ``ToolCallArgsEvaluator`` compares observed arguments to expected ones."""

OutcomeName: TypeAlias = Literal["passed", "failed", "skipped"]
"""A test item's outcome, as group aggregation consumes it."""

PhaseName: TypeAlias = Literal["setup", "call", "teardown"]
"""A pytest runtest phase."""

DEFAULT_THRESHOLD = 0.8
"""Fraction of runs that must pass when neither the transcript nor the config says.

Named once and referenced from both places that need it — ``Transcript.threshold`` and
``AgentEvalConfig.threshold`` — because the literal was previously spelled in three.
``load_transcript`` is the third: it now takes ``None`` for "leave the model default
alone", so it does not spell the number at all.
"""

DEFAULT_RUNS = 1
"""Times to execute a transcript when neither the transcript nor the config says."""


@dataclass(frozen=True, slots=True, eq=False)
class Message(Mapping[str, str]):
    """One conversation message in OpenAI format.

    A dataclass, so our own code reads ``msg.content`` rather than indexing a dict by
    string key. Also a ``Mapping``, because the ``history`` handed to user-written
    agents and evaluators has always been subscriptable and must stay so:
    ``history[-1]["content"]`` is what every example in the docs does.

    ``eq=False`` lets ``Mapping.__eq__`` take over, so a Message compares equal to the
    plain dict it replaces — which is what makes the swap invisible to callers.

    Args:
        role: Who produced the message.
        content: The message text.
        audio: WAV path a voice adapter should stream. Plugin-internal — never sent to
            a text API, which is why ``to_dict`` drops it by default.
    """

    role: Role
    content: str
    audio: str | None = None

    def __getitem__(self, key: str) -> str:
        """Return a field by name, raising KeyError when it is unset."""
        if key not in _MESSAGE_FIELDS:
            raise KeyError(key)
        value = getattr(self, key)
        if value is None:
            raise KeyError(key)
        return str(value)

    def __iter__(self) -> Iterator[str]:
        """Yield the keys that are actually set, skipping an absent audio path."""
        yield "role"
        yield "content"
        if self.audio is not None:
            yield "audio"

    def __len__(self) -> int:
        """Count the keys that are actually set."""
        return 3 if self.audio is not None else 2

    def to_dict(self, *, include_audio: bool = False) -> dict[str, str]:
        """Plain dict for an SDK boundary; drops the plugin-internal audio key by default.

        Every serialisation boundary has to say this out loud, because ``json.dumps`` on
        a Message raises. That is deliberate: it is what stops the internal shape from
        leaking into a provider request.
        """
        return {key: self[key] for key in self if include_audio or key != "audio"}


_MESSAGE_FIELDS = frozenset({"role", "content", "audio"})

History: TypeAlias = list[Message]
"""Accumulated conversation, oldest first."""

AgentCallable: TypeAlias = Callable[[History], Awaitable["tuple[str, ToolCalls]"]]
"""What the plugin calls to get one turn out of an agent.

Declared as the plain tuple rather than :class:`AgentReply`: return covariance means an
adapter returning ``AgentReply`` satisfies this, while a hand-written agent returning a
plain tuple also does. One alias, no union.
"""


class AgentReply(NamedTuple):
    """What one turn of an agent produced.

    A ``NamedTuple``, so ``reply, tool_calls = await agent(history)`` keeps working
    unchanged while the fields also have names. Adapters return this; the agent
    *contract* stays the wider plain tuple, so a hand-written
    ``async def agent(history) -> tuple[str, list[str]]`` remains valid.

    Args:
        reply: The agent's text reply for this turn.
        tool_calls: Tools called during the turn. Plain strings are accepted; the
            runner normalises them to ``ToolCall`` with ``args=None``.
    """

    reply: str
    tool_calls: ToolCalls


@dataclass(frozen=True, slots=True)
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

    __slots__ = ("args",)

    args: ToolArgs | None

    def __new__(cls, name: str, args: ToolArgs | None = None) -> ToolCall:
        """Create a ToolCall from a tool name and optional captured arguments."""
        obj = super().__new__(cls, name)
        obj.args = args
        return obj

    @property
    def name(self) -> str:
        """The tool name (the string value itself)."""
        return str(self)


@dataclass(frozen=True, slots=True)
class TurnContext:
    """Context passed to every evaluator for a turn.

    Args:
        user: The user message for this turn.
        reply: The agent's reply.
        tool_calls: Tools called during the turn. Each entry is a ToolCall
            (str-compatible); ``.args`` holds captured arguments or None.
        history: Full conversation history, up to but not including the assistant
            reply for this turn. Each entry is a :class:`Message` — attribute access
            (``m.content``) and subscripting (``m["content"]``) both work.
    """

    user: str
    reply: str
    tool_calls: list[ToolCall]
    history: History


@dataclass(frozen=True, slots=True)
class TurnResult:
    """Aggregated result for a single turn across all evaluators."""

    turn_index: int
    passed: bool
    eval_results: list[EvalResult]


@dataclass(frozen=True, slots=True)
class RunResult:
    """Result of one full run of a transcript (all turns)."""

    run_index: int
    passed: bool
    turn_results: list[TurnResult]


@dataclass(frozen=True, slots=True)
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


@runtime_checkable
class Evaluator(Protocol):
    """Protocol that all evaluators must satisfy.

    Implement this protocol to create custom evaluators. Defined here, alongside the
    types it references, so ``Expect.evaluators`` can name it without a circular import;
    re-exported from ``pytest_agent_eval.evaluators.base`` for back-compatibility.

    Example:
        ```python
        @dataclass
        class MyEvaluator:
            expected_tone: str

            async def evaluate(self, ctx: TurnContext) -> EvalResult:
                if self.expected_tone in ctx.reply.lower():
                    return EvalResult(passed=True)
                return EvalResult(passed=False, reasoning="Expected tone not found")
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


class _StrictModel(BaseModel):
    """Base for every type parsed from an external document.

    ``extra="forbid"`` is the point: a typo'd field in a transcript would otherwise
    silently disable the assertion it was meant to express. ``arbitrary_types_allowed``
    is needed for ``Expect.evaluators``, which holds user objects.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True, arbitrary_types_allowed=True)


def _reject_non_numeric(value: object) -> object:
    """Reject bools and strings before lax coercion silently accepts them.

    Verified against pydantic 2.13: lax mode reads ``threshold: true`` as 1.0 and
    ``threshold: "0.5"`` as 0.5, both of which today's validation rejects. A YAML author
    writing either meant something else.
    """
    if isinstance(value, bool | str):
        raise ValueError("must be a number, not a boolean or string")
    return value


def _valid_regex(pattern: str) -> str:
    """Reject a pattern that will not compile, at load time rather than mid-run."""
    try:
        re.compile(pattern, re.IGNORECASE)
    except re.error as exc:
        raise ValueError(f"invalid regex pattern {pattern!r}: {exc}") from exc
    return pattern


RegexPattern: TypeAlias = Annotated[str, AfterValidator(_valid_regex)]
"""A regex validated per item, so the error names the offending index."""


class JudgeConfig(_StrictModel):
    """Judge configuration for a YAML transcript turn.

    Args:
        rubric: The rubric string passed to the LLM judge.
        model: Optional pydantic-ai model ID override (e.g. "openai:gpt-4o"), or a
            pydantic-ai ``Model`` instance. Falls back to [tool.agent_eval] model if None.
    """

    rubric: str
    # A Model instance, not just an ID: the SDK test models are passed this way, and the
    # Python API has always accepted them even though the annotation said otherwise.
    model: str | Model | None = None


class ToolCallArgsConfig(_StrictModel):
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
    args: JsonMapping | None = None
    mode: ToolCallArgsMode = "subset"
    judge: JudgeConfig | None = None

    @model_validator(mode="after")
    def _needs_args_or_judge(self) -> ToolCallArgsConfig:
        """An entry with neither is a silently vacuous assertion."""
        if self.args is None and self.judge is None:
            raise ValueError(
                f"tool_calls_args entry for {self.tool!r} needs 'args' (deterministic check) "
                "or 'judge' (LLM-judged rubric); got neither"
            )
        return self


class Expect(_StrictModel):
    """Expectations for a single transcript turn.

    Args:
        evaluators: Programmatic evaluators (Python API). Excluded from serialisation
            and from the JSON schema, since they are Python objects.
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

    # SkipJsonSchema because arbitrary user objects have no JSON representation; exclude
    # because they must not appear in a serialised transcript. With Evaluator being
    # runtime_checkable, pydantic isinstance-checks each entry — a stronger constraint
    # than the list[Any] this replaces.
    evaluators: Annotated[list[Evaluator], SkipJsonSchema(), Field(default_factory=list, exclude=True)]
    judge: JudgeConfig | None = None
    tool_calls_include: list[str] = Field(default_factory=list)
    tool_calls_exclude: list[str] = Field(default_factory=list)
    tool_calls_ordered: bool = False
    tool_calls_args: list[ToolCallArgsConfig] = Field(default_factory=list)
    reply_contains_any: list[str] = Field(default_factory=list)
    reply_contains_all: list[str] = Field(default_factory=list)
    reply_matches_any: list[RegexPattern] = Field(default_factory=list)
    reply_matches_all: list[RegexPattern] = Field(default_factory=list)


class Turn(_StrictModel):
    """A single turn in a transcript.

    Args:
        user: The user message (also used as the transcript when ``audio`` is set).
        audio: Optional path to a WAV file for voice adapters. Resolved relative to
            the YAML file's directory when loaded from YAML.
        expect: Expectations for the agent's reply.
    """

    user: str
    # WithJsonSchema keeps the published schema saying "string"; a bare Path field emits
    # {"format": "path"}, which editors then flag on a perfectly good transcript.
    audio: Annotated[_PathLike | None, WithJsonSchema({"type": "string"})] = None
    expect: Expect = Field(default_factory=Expect)


class Transcript(_StrictModel):
    """A multi-turn evaluation transcript.

    Args:
        id: Unique identifier used as the pytest test name.
        turns: Ordered list of turns.
        threshold: Fraction of runs that must pass (0.0-1.0).
        runs: Number of times to execute this transcript.
        tags: Optional quality-gate tags (e.g. ["gate:booking"]).
    """

    id: str
    turns: list[Turn] = Field(min_length=1)
    threshold: float = Field(default=DEFAULT_THRESHOLD, ge=0.0, le=1.0)
    runs: int = Field(default=DEFAULT_RUNS, ge=1)
    tags: list[str] = Field(default_factory=list)

    _reject_bad_numbers = field_validator("threshold", "runs", mode="before")(_reject_non_numeric)
