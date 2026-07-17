"""Tests for LiveKitAdapter using a fake AgentSession (no real LiveKit calls)."""

from __future__ import annotations

import asyncio
import wave
from pathlib import Path
from typing import Any

import pytest

from pytest_agent_eval.adapters import livekit as livekit_module
from pytest_agent_eval.adapters.livekit import LiveKitAdapter


class _FakeWavInput:
    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        self._exhausted = asyncio.Event()
        self.closed = False
        self._exhausted.set()

    async def wait_for_exhaustion(self) -> None:
        await self._exhausted.wait()

    async def aclose(self) -> None:
        self.closed = True


class _FakeInputContainer:
    def __init__(self) -> None:
        self.audio: Any = None


class _FakeFunctionCall:
    def __init__(self, name: str, arguments: str | None = None) -> None:
        self.name = name
        if arguments is not None:
            self.arguments = arguments


class _FakeFunctionToolsExecutedEvent:
    def __init__(self, names: list[str], arguments: str | None = None) -> None:
        self.function_calls = [_FakeFunctionCall(n, arguments) for n in names]


class _FakeChatItem:
    def __init__(self, role: str, text: str) -> None:
        self.role = role
        self.text_content = text


class _FakeConversationItemAddedEvent:
    def __init__(self, role: str, text: str) -> None:
        self.item = _FakeChatItem(role, text)


class FakeAgentSession:
    """Records callbacks; fires scripted events when ``start`` is called."""

    def __init__(
        self,
        *,
        tool_names: list[str] | None = None,
        reply_chunks: list[str] | None = None,
    ) -> None:
        self.input = _FakeInputContainer()
        self._handlers: dict[str, list[Any]] = {}
        self._tool_names = tool_names or []
        self._reply_chunks = reply_chunks or []
        self.started = False
        self.closed = False

    def on(self, event: str, handler: Any) -> None:
        self._handlers.setdefault(event, []).append(handler)

    async def start(self, agent: Any) -> None:
        self.started = True
        for chunk in self._reply_chunks:
            for h in self._handlers.get("conversation_item_added", []):
                h(_FakeConversationItemAddedEvent("assistant", chunk))
        if self._tool_names:
            for h in self._handlers.get("function_tools_executed", []):
                h(_FakeFunctionToolsExecutedEvent(self._tool_names))

    async def aclose(self) -> None:
        self.closed = True


def _write_dummy_wav(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24_000)
        w.writeframes(b"\x00\x00" * 100)


@pytest.fixture
def patched_wav_input(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(livekit_module, "WavFileAudioInput", _FakeWavInput)


async def test_captures_tool_calls_and_reply(tmp_path: Path, patched_wav_input: None) -> None:
    wav_path = tmp_path / "turn.wav"
    _write_dummy_wav(wav_path)
    fake = FakeAgentSession(tool_names=["create_booking"], reply_chunks=["confirmed!"])

    def factory() -> tuple[Any, Any]:
        return fake, object()

    adapter = LiveKitAdapter(factory, grace_period_s=0.0, timeout_s=1.0)
    history = [{"role": "user", "content": "book me", "audio": str(wav_path)}]

    reply, tool_calls = await adapter(history)

    assert reply == "confirmed!"
    assert tool_calls == ["create_booking"]
    assert fake.started
    assert fake.closed


async def test_captures_tool_call_arguments_when_present(tmp_path: Path, patched_wav_input: None) -> None:
    wav_path = tmp_path / "turn.wav"
    _write_dummy_wav(wav_path)

    class FakeWithArgs(FakeAgentSession):
        async def start(self, agent: Any) -> None:
            self.started = True
            for h in self._handlers.get("function_tools_executed", []):
                h(_FakeFunctionToolsExecutedEvent(["create_booking"], arguments='{"time": "10am"}'))

    adapter = LiveKitAdapter(lambda: (FakeWithArgs(), object()), grace_period_s=0.0, timeout_s=1.0)
    _, tool_calls = await adapter([{"role": "user", "content": "hi", "audio": str(wav_path)}])

    assert tool_calls == ["create_booking"]
    assert tool_calls[0].args == {"time": "10am"}


async def test_tool_call_without_arguments_degrades_to_none(tmp_path: Path, patched_wav_input: None) -> None:
    wav_path = tmp_path / "turn.wav"
    _write_dummy_wav(wav_path)
    fake = FakeAgentSession(tool_names=["create_booking"])

    adapter = LiveKitAdapter(lambda: (fake, object()), grace_period_s=0.0, timeout_s=1.0)
    _, tool_calls = await adapter([{"role": "user", "content": "hi", "audio": str(wav_path)}])

    assert tool_calls[0].args is None


async def test_concatenates_multiple_reply_chunks(tmp_path: Path, patched_wav_input: None) -> None:
    wav_path = tmp_path / "turn.wav"
    _write_dummy_wav(wav_path)
    fake = FakeAgentSession(reply_chunks=["hello", " ", "world"])

    adapter = LiveKitAdapter(lambda: (fake, object()), grace_period_s=0.0, timeout_s=1.0)
    reply, _ = await adapter([{"role": "user", "content": "hi", "audio": str(wav_path)}])

    assert reply == "hello world"


async def test_ignores_user_role_items(tmp_path: Path, patched_wav_input: None) -> None:
    wav_path = tmp_path / "turn.wav"
    _write_dummy_wav(wav_path)

    class FakeWithUserItem(FakeAgentSession):
        async def start(self, agent: Any) -> None:
            self.started = True
            for h in self._handlers.get("conversation_item_added", []):
                h(_FakeConversationItemAddedEvent("user", "this should be ignored"))
                h(_FakeConversationItemAddedEvent("assistant", "actual reply"))

    fake = FakeWithUserItem()
    adapter = LiveKitAdapter(lambda: (fake, object()), grace_period_s=0.0, timeout_s=1.0)
    reply, _ = await adapter([{"role": "user", "content": "hi", "audio": str(wav_path)}])

    assert reply == "actual reply"


async def test_missing_audio_raises(patched_wav_input: None) -> None:
    adapter = LiveKitAdapter(lambda: (FakeAgentSession(), object()))
    with pytest.raises(ValueError, match="requires Turn.audio"):
        await adapter([{"role": "user", "content": "hi"}])


async def test_missing_wav_file_raises(tmp_path: Path, patched_wav_input: None) -> None:
    adapter = LiveKitAdapter(lambda: (FakeAgentSession(), object()))
    with pytest.raises(FileNotFoundError, match="WAV fixture missing"):
        await adapter([{"role": "user", "content": "hi", "audio": str(tmp_path / "missing.wav")}])


async def test_history_must_end_with_user_turn(patched_wav_input: None) -> None:
    adapter = LiveKitAdapter(lambda: (FakeAgentSession(), object()))
    with pytest.raises(ValueError, match="must end with a user turn"):
        await adapter([{"role": "assistant", "content": "hello"}])


async def test_factory_called_per_invocation(tmp_path: Path, patched_wav_input: None) -> None:
    wav_path = tmp_path / "turn.wav"
    _write_dummy_wav(wav_path)

    sessions: list[FakeAgentSession] = []

    def factory() -> tuple[Any, Any]:
        s = FakeAgentSession(reply_chunks=["ok"])
        sessions.append(s)
        return s, object()

    adapter = LiveKitAdapter(factory, grace_period_s=0.0, timeout_s=1.0)
    msg = {"role": "user", "content": "hi", "audio": str(wav_path)}
    await adapter([msg])
    await adapter([msg])

    assert len(sessions) == 2


async def test_sample_rate_and_frame_ms_passed_to_wav_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wav_path = tmp_path / "turn.wav"
    _write_dummy_wav(wav_path)

    captured: dict[str, Any] = {}

    class CapturingWav(_FakeWavInput):
        def __init__(self, path: Any, *, sample_rate: int, frame_ms: int) -> None:
            super().__init__()
            captured["path"] = path
            captured["sample_rate"] = sample_rate
            captured["frame_ms"] = frame_ms

    monkeypatch.setattr(livekit_module, "WavFileAudioInput", CapturingWav)

    adapter = LiveKitAdapter(
        lambda: (FakeAgentSession(), object()),
        sample_rate=16_000,
        frame_ms=40,
        grace_period_s=0.0,
        timeout_s=1.0,
    )
    await adapter([{"role": "user", "content": "hi", "audio": str(wav_path)}])

    assert captured["sample_rate"] == 16_000
    assert captured["frame_ms"] == 40
    assert Path(captured["path"]) == wav_path
