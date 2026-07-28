"""In-process agent callables satisfying the agent contract.

The runner tests each declared their own ``async def agent`` closure; the recurring
shapes live here instead. Anything genuinely one-off stays local to its test.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field


async def echo_agent(history: list[dict]) -> tuple[str, list[str]]:
    """Echo the last user message back, calling no tools."""
    return history[-1]["content"], []


async def booking_agent(history: list[dict]) -> tuple[str, list[str]]:
    """Return a booking confirmation and record one ``book_slot`` call."""
    return "Your slot is confirmed for tomorrow at 10am.", ["book_slot"]


def static_agent(reply: str = "ok", tool_calls: Sequence[str] = ()) -> object:
    """Build an agent that always answers ``reply`` with ``tool_calls``."""

    async def agent(history: list[dict]) -> tuple[str, list[str]]:
        return reply, list(tool_calls)

    return agent


@dataclass
class RecordingAgent:
    """Agent that records the history it was handed on each turn.

    Stores a copy per turn, so a test can assert on what the agent saw at the time
    rather than on the accumulated list afterwards.
    """

    reply: str = "ok"
    tool_calls: Sequence[str] = ()
    seen: list[list[dict]] = field(default_factory=list)

    async def __call__(self, history: list[dict]) -> tuple[str, list[str]]:
        """Record a snapshot of history, then answer."""
        self.seen.append([dict(m) for m in history])
        return self.reply, list(self.tool_calls)

    @property
    def last_message(self) -> dict:
        """The final message of the most recent turn's history."""
        return self.seen[-1][-1]


@dataclass
class ScriptedAgent:
    """Agent that returns each scripted reply in turn, repeating the last one.

    Replaces the hand-rolled ``nonlocal call_count`` counters used to model a flaky
    agent across repeated runs.
    """

    replies: Sequence[str]
    tool_calls: Sequence[str] = ()
    calls: int = 0

    async def __call__(self, history: list[dict]) -> tuple[str, list[str]]:
        """Answer with the next scripted reply."""
        reply = self.replies[min(self.calls, len(self.replies) - 1)]
        self.calls += 1
        return reply, list(self.tool_calls)
