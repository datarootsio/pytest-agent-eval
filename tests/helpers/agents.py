"""In-process agent callables satisfying the agent contract.

The runner tests each declared their own ``async def agent`` closure; the recurring
shapes live here instead. Anything genuinely one-off stays local to its test.

These are also the canonical example of what an agent looks like, so they use the typed
forms: ``history[-1].content`` and ``AgentReply(...)``. The plain-tuple return and
``history[-1]["content"]`` still work — ``tests/test_message.py`` pins that — but a helper
the whole suite reads should show the shape we recommend.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from pytest_agent_eval.models import AgentCallable, AgentReply, History, Message


async def echo_agent(history: History) -> AgentReply:
    """Echo the last user message back, calling no tools."""
    return AgentReply(history[-1].content, [])


async def booking_agent(history: History) -> AgentReply:
    """Return a booking confirmation and record one ``book_slot`` call."""
    return AgentReply("Your slot is confirmed for tomorrow at 10am.", ["book_slot"])


def static_agent(reply: str = "ok", tool_calls: Sequence[str] = ()) -> AgentCallable:
    """Build an agent that always answers ``reply`` with ``tool_calls``."""

    async def agent(history: History) -> AgentReply:
        return AgentReply(reply, list(tool_calls))

    return agent


@dataclass
class RecordingAgent:
    """Agent that records the history it was handed on each turn.

    Stores a copy per turn, so a test can assert on what the agent saw at the time
    rather than on the accumulated list afterwards.
    """

    reply: str = "ok"
    tool_calls: Sequence[str] = ()
    seen: list[History] = field(default_factory=list)

    async def __call__(self, history: History) -> AgentReply:
        """Record a snapshot of history, then answer."""
        # list(history), not [dict(m) for m in history]. The dict copy downgraded the
        # Messages the runner had just built, which is what forced every assertion on a
        # recorded turn to read by string key. Message is frozen, so a shallow copy is
        # already a true snapshot.
        self.seen.append(list(history))
        return AgentReply(self.reply, list(self.tool_calls))

    @property
    def last_message(self) -> Message:
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

    async def __call__(self, history: History) -> AgentReply:
        """Answer with the next scripted reply."""
        reply = self.replies[min(self.calls, len(self.replies) - 1)]
        self.calls += 1
        return AgentReply(reply, list(self.tool_calls))
