"""Recording test doubles.

Typed classes with frozen call records rather than mutable spy dicts threaded
through signatures, so what was recorded is visible at the assertion site.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SynthCall:
    """One recorded synthesis request."""

    text: str
    voice: str
    model: str


class SynthSpy:
    """Records synthesis requests and returns canned PCM.

    Injected through ``_run``'s ``synth``/``client_factory`` parameters rather than
    monkeypatched onto the module, so the tests exercise the real call path.
    """

    def __init__(self, *, fail_with: BaseException | None = None, fail_times: int | None = None) -> None:
        self.calls: list[SynthCall] = []
        self._fail_with = fail_with
        self._fail_times = fail_times
        self.client_closed = False

    def client_factory(self) -> Any:
        spy = self

        class FakeClient:
            async def close(self) -> None:
                spy.client_closed = True

        return FakeClient()

    async def __call__(self, client: Any, *, text: str, voice: str, model: str) -> bytes:
        self.calls.append(SynthCall(text=text, voice=voice, model=model))
        if self._fail_with is not None and (self._fail_times is None or len(self.calls) <= self._fail_times):
            raise self._fail_with
        return b"\x00\x01" * 1000

    @property
    def count(self) -> int:
        return len(self.calls)
