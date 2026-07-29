"""Fakes for smolagents agents.

Duck-typed against ``.run(task, reset=...)`` and ``.memory.steps``, which is all the
adapter requires.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RunCall:
    """One recorded ``agent.run`` invocation.

    Named rather than a bare ``(str, bool)`` tuple: ``reset`` is the whole point of
    these tests — it is how the adapter signals a fresh transcript — and an anonymous
    second element made that invisible at the assertion site.
    """

    task: str
    reset: bool


class FakeSmolagent:
    """Records run calls and appends scripted memory steps.

    Args:
        reply: What ``run`` returns.
        new_steps: Memory steps appended to ``memory.steps`` on each run.
    """

    def __init__(self, reply: Any = "ok", new_steps: Sequence[Any] | None = None) -> None:
        self.memory = _FakeMemory()
        self.calls: list[RunCall] = []
        self._reply = reply
        self._new_steps = list(new_steps or [])

    def run(self, task: str, reset: bool = True) -> Any:
        """Record the call, apply the reset semantics, and return the scripted reply."""
        self.calls.append(RunCall(task=task, reset=reset))
        if reset:
            self.memory.steps = []
        self.memory.steps.extend(self._new_steps)
        return self._reply

    @property
    def tasks(self) -> list[str]:
        """The task string of every recorded run."""
        return [call.task for call in self.calls]


@dataclass
class _FakeMemory:
    steps: list[Any] = field(default_factory=list)


@dataclass(frozen=True)
class FakeToolCall:
    """A smolagents-style tool call carrying its arguments."""

    name: str
    arguments: Any = None


@dataclass(frozen=True)
class FakeStep:
    """A memory step holding the tool calls executed during it."""

    tool_calls: Sequence[Any] = ()
