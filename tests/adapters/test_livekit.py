"""Tests for LiveKitAdapter against a scripted fake AgentSession (no real LiveKit calls)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from pytest_agent_eval.adapters import livekit as livekit_module
from pytest_agent_eval.adapters.livekit import LiveKitAdapter
from pytest_agent_eval.models import Message
from tests.helpers.livekit_fakes import (
    FakeAgentSession,
    FakeWavInput,
    assistant_content_parts,
    assistant_says,
    item_missing,
    tools_executed,
    user_says,
    wav_input_factory,
    write_silent_wav,
)


@pytest.fixture
def wav_input(monkeypatch: pytest.MonkeyPatch) -> FakeWavInput:
    """Install a fake WavFileAudioInput and hand the test the instance it will get."""
    fake = FakeWavInput()
    monkeypatch.setattr(livekit_module, "WavFileAudioInput", wav_input_factory(fake))
    return fake


def _adapter(session: FakeAgentSession, **kwargs: Any) -> LiveKitAdapter:
    defaults: dict[str, Any] = {"grace_period_s": 0.0, "timeout_s": 1.0}
    return LiveKitAdapter(lambda: (session, object()), **{**defaults, **kwargs})


def _voice_turn(wav_path: Path, content: str = "hi") -> list[dict[str, str]]:
    return [Message(role="user", content=content, audio=str(wav_path))]


# --- capture ---


async def test_captures_tool_calls_and_reply(tmp_path: Path, wav_input: FakeWavInput) -> None:
    session = FakeAgentSession(events=[assistant_says("confirmed!"), tools_executed("create_booking")])

    reply, tool_calls = await _adapter(session)(_voice_turn(write_silent_wav(tmp_path / "turn.wav"), "book me"))

    assert reply == "confirmed!"
    assert tool_calls == ["create_booking"]
    assert session.started
    assert session.closed


async def test_captures_tool_call_arguments_when_present(tmp_path: Path, wav_input: FakeWavInput) -> None:
    session = FakeAgentSession(events=[tools_executed(("create_booking", '{"time": "10am"}'))])

    _, tool_calls = await _adapter(session)(_voice_turn(write_silent_wav(tmp_path / "turn.wav")))

    assert tool_calls == ["create_booking"]
    assert tool_calls[0].args == {"time": "10am"}


async def test_tool_call_without_arguments_degrades_to_none(tmp_path: Path, wav_input: FakeWavInput) -> None:
    session = FakeAgentSession(events=[tools_executed("create_booking")])

    _, tool_calls = await _adapter(session)(_voice_turn(write_silent_wav(tmp_path / "turn.wav")))

    assert tool_calls[0].args is None


async def test_unnamed_tool_calls_are_dropped(tmp_path: Path, wav_input: FakeWavInput) -> None:
    """A call event can arrive before the name is known; an empty name is not a tool."""
    session = FakeAgentSession(events=[tools_executed("", "real_tool")])

    _, tool_calls = await _adapter(session)(_voice_turn(write_silent_wav(tmp_path / "turn.wav")))

    assert tool_calls == ["real_tool"]


async def test_concatenates_multiple_reply_chunks(tmp_path: Path, wav_input: FakeWavInput) -> None:
    session = FakeAgentSession(events=[assistant_says("hello"), assistant_says(" "), assistant_says("world")])

    reply, _ = await _adapter(session)(_voice_turn(write_silent_wav(tmp_path / "turn.wav")))

    assert reply == "hello world"


async def test_ignores_user_role_items(tmp_path: Path, wav_input: FakeWavInput) -> None:
    session = FakeAgentSession(events=[user_says("this should be ignored"), assistant_says("actual reply")])

    reply, _ = await _adapter(session)(_voice_turn(write_silent_wav(tmp_path / "turn.wav")))

    assert reply == "actual reply"


async def test_ignores_events_without_an_item(tmp_path: Path, wav_input: FakeWavInput) -> None:
    session = FakeAgentSession(events=[item_missing(), assistant_says("real reply")])

    reply, _ = await _adapter(session)(_voice_turn(write_silent_wav(tmp_path / "turn.wav")))

    assert reply == "real reply"


async def test_falls_back_to_content_parts_when_text_content_is_empty(tmp_path: Path, wav_input: FakeWavInput) -> None:
    """Some chat items expose their text only as a content list; non-str parts are skipped."""
    session = FakeAgentSession(events=[assistant_content_parts("Boo", None, "ked!")])

    reply, _ = await _adapter(session)(_voice_turn(write_silent_wav(tmp_path / "turn.wav")))

    assert reply == "Booked!"


async def test_assistant_items_with_no_text_are_dropped(tmp_path: Path, wav_input: FakeWavInput) -> None:
    session = FakeAgentSession(events=[assistant_content_parts(None, 42)])

    reply, _ = await _adapter(session)(_voice_turn(write_silent_wav(tmp_path / "turn.wav")))

    assert reply == ""


# --- input validation ---


async def test_missing_audio_raises(wav_input: FakeWavInput) -> None:
    with pytest.raises(ValueError, match="requires Turn.audio"):
        await _adapter(FakeAgentSession())([Message(role="user", content="hi")])


async def test_missing_wav_file_raises(tmp_path: Path, wav_input: FakeWavInput) -> None:
    with pytest.raises(FileNotFoundError, match="WAV fixture missing"):
        await _adapter(FakeAgentSession())([Message(role="user", content="hi", audio=str(tmp_path / "gone.wav"))])


async def test_history_must_end_with_user_turn(wav_input: FakeWavInput) -> None:
    with pytest.raises(ValueError, match="must end with a user turn"):
        await _adapter(FakeAgentSession())([Message(role="assistant", content="hello")])


# --- session lifecycle ---


async def test_factory_called_per_invocation(tmp_path: Path, wav_input: FakeWavInput) -> None:
    sessions: list[FakeAgentSession] = []

    def factory() -> tuple[Any, Any]:
        session = FakeAgentSession(events=[assistant_says("ok")])
        sessions.append(session)
        return session, object()

    adapter = LiveKitAdapter(factory, grace_period_s=0.0, timeout_s=1.0)
    turn = _voice_turn(write_silent_wav(tmp_path / "turn.wav"))
    await adapter(turn)
    await adapter(turn)

    assert len(sessions) == 2


async def test_sample_rate_and_frame_ms_passed_to_wav_input(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeWavInput()
    monkeypatch.setattr(livekit_module, "WavFileAudioInput", wav_input_factory(fake))
    wav_path = write_silent_wav(tmp_path / "turn.wav")

    await _adapter(FakeAgentSession(), sample_rate=16_000, frame_ms=40)(_voice_turn(wav_path))

    assert fake.constructed_with["sample_rate"] == 16_000
    assert fake.constructed_with["frame_ms"] == 40
    assert Path(fake.constructed_with["path"]) == wav_path


async def test_wav_exhaustion_timeout_is_survivable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A model that never drains the WAV must not hang the suite — the turn still returns."""
    monkeypatch.setattr(
        livekit_module, "WavFileAudioInput", wav_input_factory(FakeWavInput(exhausted_immediately=False))
    )
    session = FakeAgentSession(events=[assistant_says("partial")])

    reply, _ = await _adapter(session, timeout_s=0.01)(_voice_turn(write_silent_wav(tmp_path / "turn.wav")))

    assert reply == "partial"
    assert session.closed


async def test_wav_input_close_failure_does_not_mask_the_reply(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Cleanup failures are logged, never raised — they would otherwise discard a good turn."""
    monkeypatch.setattr(
        livekit_module,
        "WavFileAudioInput",
        wav_input_factory(FakeWavInput(close_error=RuntimeError("aclose blew up"))),
    )
    session = FakeAgentSession(events=[assistant_says("confirmed")])

    reply, _ = await _adapter(session)(_voice_turn(write_silent_wav(tmp_path / "turn.wav")))

    assert reply == "confirmed"
    # The session must still be closed even though the wav input's close raised.
    assert session.closed


async def test_session_close_failure_does_not_mask_the_reply(tmp_path: Path, wav_input: FakeWavInput) -> None:
    session = FakeAgentSession(events=[assistant_says("ok")], close_error=RuntimeError("session aclose blew up"))

    reply, _ = await _adapter(session)(_voice_turn(write_silent_wav(tmp_path / "turn.wav")))

    assert reply == "ok"
