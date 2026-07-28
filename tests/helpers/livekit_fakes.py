"""Fakes for LiveKit voice sessions.

LiveKit's real event objects need a running session to construct, so the adapter is
tested against these. The session takes a *script* of events to fire on ``start``,
which replaced seven near-identical subclasses that each overrode ``start`` only to
emit a different event.
"""

from __future__ import annotations

import asyncio
import wave
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any


@dataclass(frozen=True)
class ToolCallEvent:
    """A ``function_tools_executed`` event carrying one or more executed calls."""

    calls: Sequence[tuple[str, str | None]]

    @property
    def function_calls(self) -> list[Any]:
        """The event's function_calls, mirroring LiveKit's attribute name."""
        return [_function_call(name, arguments) for name, arguments in self.calls]


def _function_call(name: str, arguments: str | None) -> Any:
    # The only SimpleNamespace fake kept on purpose: when arguments is None the
    # attribute must be *absent*, which is what exercises the adapter's
    # getattr(fc, "arguments", None) default. A dataclass always has the attribute.
    return SimpleNamespace(name=name) if arguments is None else SimpleNamespace(name=name, arguments=arguments)


def tools_executed(*calls: str | tuple[str, str | None]) -> ToolCallEvent:
    """Build a tools-executed event from names, or (name, json_arguments) pairs."""
    return ToolCallEvent(calls=[(c, None) if isinstance(c, str) else c for c in calls])


def assistant_says(text: str) -> Any:
    """A conversation item from the assistant, exposing ``text_content``."""
    return SimpleNamespace(item=SimpleNamespace(role="assistant", text_content=text))


def user_says(text: str) -> Any:
    """A conversation item from the user, which the adapter must ignore."""
    return SimpleNamespace(item=SimpleNamespace(role="user", text_content=text))


def assistant_content_parts(*parts: Any) -> Any:
    """An assistant item whose text is only available as a content list."""
    return SimpleNamespace(item=SimpleNamespace(role="assistant", text_content=None, content=list(parts)))


def item_missing() -> Any:
    """A conversation event that arrived with no item attached."""
    return SimpleNamespace(item=None)


_CONVERSATION_EVENT = "conversation_item_added"
_TOOLS_EVENT = "function_tools_executed"


class FakeAgentSession:
    """Records handlers, then fires a scripted event sequence when ``start`` is called.

    Args:
        events: Events to emit on ``start``, in order. A :class:`ToolCallEvent` goes to
            the tools handler; anything else goes to the conversation handler.
        close_error: Raised by ``aclose`` to exercise the adapter's cleanup path.
    """

    def __init__(self, *, events: Sequence[Any] = (), close_error: BaseException | None = None) -> None:
        self.input = SimpleNamespace(audio=None)
        self._handlers: dict[str, list[Any]] = {}
        self._events = list(events)
        self._close_error = close_error
        self.started = False
        self.closed = False

    def on(self, event: str, handler: Any) -> None:
        """Register a handler, as LiveKit's AgentSession does."""
        self._handlers.setdefault(event, []).append(handler)

    async def start(self, agent: Any) -> None:
        """Fire every scripted event at the matching handler."""
        self.started = True
        for event in self._events:
            name = _TOOLS_EVENT if isinstance(event, ToolCallEvent) else _CONVERSATION_EVENT
            for handler in self._handlers.get(name, []):
                handler(event)

    async def aclose(self) -> None:
        """Mark the session closed, or raise the configured cleanup error."""
        self.closed = True
        if self._close_error is not None:
            raise self._close_error


@dataclass
class FakeWavInput:
    """Stand-in for WavFileAudioInput.

    Args:
        exhausted_immediately: When False, ``wait_for_exhaustion`` never returns, which
            is how the adapter's timeout path is reached.
        close_error: Raised by ``aclose`` to exercise the adapter's cleanup path.
    """

    exhausted_immediately: bool = True
    close_error: BaseException | None = None
    closed: bool = False
    constructed_with: dict[str, Any] = field(default_factory=dict)
    _event: asyncio.Event = field(default_factory=asyncio.Event, init=False, repr=False)

    def __post_init__(self) -> None:
        """Pre-set the exhaustion event unless the test wants a stall."""
        if self.exhausted_immediately:
            self._event.set()

    async def wait_for_exhaustion(self) -> None:
        """Block until the WAV has drained."""
        await self._event.wait()

    async def aclose(self) -> None:
        """Mark closed, or raise the configured cleanup error."""
        self.closed = True
        if self.close_error is not None:
            raise self.close_error


def wav_input_factory(prototype: FakeWavInput) -> Any:
    """Return a WavFileAudioInput stand-in that records its construction arguments."""

    def build(path: Any, *, sample_rate: int = 24_000, frame_ms: int = 20) -> FakeWavInput:
        prototype.constructed_with = {"path": path, "sample_rate": sample_rate, "frame_ms": frame_ms}
        return prototype

    return build


def write_silent_wav(path: Path, *, frames: int = 100) -> Path:
    """Write a tiny mono 16-bit 24 kHz WAV, the format the adapter requires."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24_000)
        w.writeframes(b"\x00\x00" * frames)
    return path
