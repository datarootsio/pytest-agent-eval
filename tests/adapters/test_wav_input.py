"""Tests for the WAV-backed LiveKit AudioInput.

Driven against a fake ``livekit`` injected into ``sys.modules`` rather than the real
package. Faking an *external* boundary keeps the coverage gate extras-independent —
`livekit` is an optional extra, and a gate that only reaches 100% when it happens to
be installed is not a gate. One additive smoke test builds the real thing when the
extra is present; it contributes no unique lines but would catch a livekit API move.
"""

from __future__ import annotations

import asyncio
import sys
import types
import wave
from typing import TYPE_CHECKING, Any

import pytest

from pytest_agent_eval.adapters import _wav_input

if TYPE_CHECKING:
    from pathlib import Path

_SAMPLE_RATE = 24_000
_FRAME_MS = 20
_SAMPLES_PER_FRAME = _SAMPLE_RATE * _FRAME_MS // 1000


@pytest.fixture(autouse=True)
def _reset_class_cache() -> Any:
    """Clear the memoised class between tests.

    ``_class_cache`` is a module global populated on first use and never reset, so
    the first test to seed it with a fake would otherwise hand that fake to every
    later test — including ones that mean to build the real class.
    """
    _wav_input._class_cache = None
    yield
    _wav_input._class_cache = None


class _FakeAudioFrame:
    """Stand-in for ``livekit.rtc.AudioFrame``, recording what it was handed."""

    def __init__(self, *, data: bytes, sample_rate: int, num_channels: int, samples_per_channel: int) -> None:
        self.data = data
        self.sample_rate = sample_rate
        self.num_channels = num_channels
        self.samples_per_channel = samples_per_channel


class _FakeAudioInput:
    """Stand-in for ``livekit.agents.voice.io.AudioInput``."""

    def __init__(self, label: str = "") -> None:
        self.label = label


@pytest.fixture
def fake_livekit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Install a minimal fake livekit package tree over whatever is (or isn't) installed."""
    rtc = types.ModuleType("livekit.rtc")
    rtc.AudioFrame = _FakeAudioFrame  # type: ignore[attr-defined]

    io = types.ModuleType("livekit.agents.voice.io")
    io.AudioInput = _FakeAudioInput  # type: ignore[attr-defined]

    livekit = types.ModuleType("livekit")
    livekit.rtc = rtc  # type: ignore[attr-defined]
    agents = types.ModuleType("livekit.agents")
    voice = types.ModuleType("livekit.agents.voice")
    voice.io = io  # type: ignore[attr-defined]
    agents.voice = voice  # type: ignore[attr-defined]
    livekit.agents = agents  # type: ignore[attr-defined]

    for name, module in (
        ("livekit", livekit),
        ("livekit.rtc", rtc),
        ("livekit.agents", agents),
        ("livekit.agents.voice", voice),
        ("livekit.agents.voice.io", io),
    ):
        monkeypatch.setitem(sys.modules, name, module)


def _write_wav(
    path: Path,
    *,
    samples: int = _SAMPLES_PER_FRAME,
    channels: int = 1,
    sampwidth: int = 2,
    framerate: int = _SAMPLE_RATE,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(sampwidth)
        w.setframerate(framerate)
        w.writeframes(b"\x01\x02" * samples * channels)
    return path


# --- lazy import ---


def test_import_error_names_the_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without the extra, the failure must name the install command, not an ImportError trace."""
    monkeypatch.setitem(sys.modules, "livekit", None)
    with pytest.raises(ImportError, match=r"requires the 'livekit' extra.*pytest-agent-eval\[livekit\]"):
        _wav_input._import_livekit()


def test_livekit_import_stays_lazy() -> None:
    """Importing the adapter module must not import livekit.

    examples/voice-livekit/conftest.py imports the adapter at module scope with
    livekit absent, and an example-collection test runs it.
    """
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setitem(sys.modules, "livekit", None)
    try:
        import importlib

        importlib.reload(_wav_input)  # must not raise
    finally:
        monkeypatch.undo()
        import importlib

        importlib.reload(_wav_input)


# --- the class factory ---


def test_factory_subclasses_the_livekit_audio_input(fake_livekit: None) -> None:
    cls = _wav_input._make_wav_file_audio_input_class()
    assert issubclass(cls, _FakeAudioInput)


def test_public_callable_caches_the_class(fake_livekit: None, tmp_path: Path) -> None:
    """The class is built once; livekit is imported on first construction only."""
    first = _wav_input.WavFileAudioInput(_write_wav(tmp_path / "a.wav"))
    second = _wav_input.WavFileAudioInput(_write_wav(tmp_path / "b.wav"))
    assert type(first) is type(second)
    assert _wav_input._class_cache is type(first)


def test_label_identifies_the_wav_file(fake_livekit: None, tmp_path: Path) -> None:
    stream = _wav_input.WavFileAudioInput(_write_wav(tmp_path / "turn1.wav"))
    assert stream.label == "WavFileAudioInput(turn1.wav)"


# --- WAV validation ---


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"channels": 2}, "expected mono, got 2 ch"),
        ({"sampwidth": 1}, "expected 16-bit PCM, got 8-bit"),
        ({"framerate": 16_000}, "expected 24000 Hz, got 16000 Hz"),
    ],
    ids=["stereo", "eight_bit", "wrong_rate"],
)
async def test_rejects_wav_files_the_realtime_model_cannot_use(
    fake_livekit: None, tmp_path: Path, kwargs: dict[str, Any], expected: str
) -> None:
    stream = _wav_input.WavFileAudioInput(_write_wav(tmp_path / "bad.wav", **kwargs))
    with pytest.raises(ValueError, match=expected):
        await stream.__anext__()


# --- streaming ---


async def test_streams_one_frame_per_iteration(fake_livekit: None, tmp_path: Path) -> None:
    stream = _wav_input.WavFileAudioInput(
        _write_wav(tmp_path / "t.wav", samples=_SAMPLES_PER_FRAME * 2), frame_ms=_FRAME_MS
    )

    first = await stream.__anext__()

    assert isinstance(first, _FakeAudioFrame)
    assert first.samples_per_channel == _SAMPLES_PER_FRAME
    assert first.num_channels == 1
    assert first.sample_rate == _SAMPLE_RATE
    assert len(first.data) == _SAMPLES_PER_FRAME * 2


async def test_pads_the_final_short_frame_and_marks_exhaustion(fake_livekit: None, tmp_path: Path) -> None:
    """A trailing partial frame is zero-padded so the model still receives full frames."""
    stream = _wav_input.WavFileAudioInput(_write_wav(tmp_path / "t.wav", samples=10), frame_ms=_FRAME_MS)

    frame = await stream.__anext__()

    assert len(frame.data) == _SAMPLES_PER_FRAME * 2
    assert frame.data.endswith(b"\x00\x00")
    await asyncio.wait_for(stream.wait_for_exhaustion(), timeout=1.0)


async def test_keeps_emitting_silence_after_exhaustion(fake_livekit: None, tmp_path: Path) -> None:
    """The session stays alive past the user audio so the model can finish replying."""
    stream = _wav_input.WavFileAudioInput(_write_wav(tmp_path / "t.wav", samples=10), frame_ms=_FRAME_MS)

    await stream.__anext__()
    silence = await stream.__anext__()

    assert silence.data == b"\x00" * (_SAMPLES_PER_FRAME * 2)


async def test_wait_for_exhaustion_blocks_until_the_wav_drains(fake_livekit: None, tmp_path: Path) -> None:
    """Exactly two full frames: exhaustion is signalled by the first *short* frame, the third."""
    stream = _wav_input.WavFileAudioInput(
        _write_wav(tmp_path / "t.wav", samples=_SAMPLES_PER_FRAME * 2), frame_ms=_FRAME_MS
    )
    waiter = asyncio.ensure_future(stream.wait_for_exhaustion())

    await stream.__anext__()
    await stream.__anext__()
    assert not waiter.done()

    await stream.__anext__()
    await asyncio.wait_for(waiter, timeout=1.0)


async def test_aclose_stops_iteration_and_releases_waiters(fake_livekit: None, tmp_path: Path) -> None:
    stream = _wav_input.WavFileAudioInput(
        _write_wav(tmp_path / "t.wav", samples=_SAMPLES_PER_FRAME * 100), frame_ms=_FRAME_MS
    )
    waiter = asyncio.ensure_future(stream.wait_for_exhaustion())

    await stream.aclose()

    await asyncio.wait_for(waiter, timeout=1.0)
    with pytest.raises(StopAsyncIteration):
        await stream.__anext__()


async def test_frame_size_follows_sample_rate_and_frame_ms(fake_livekit: None, tmp_path: Path) -> None:
    stream = _wav_input.WavFileAudioInput(
        _write_wav(tmp_path / "t.wav", samples=1600, framerate=16_000),
        sample_rate=16_000,
        frame_ms=40,
    )

    frame = await stream.__anext__()

    assert frame.samples_per_channel == 640
    assert frame.sample_rate == 16_000


# --- additive: the real SDK, when installed ---


def test_real_livekit_audio_input_still_subclassable(tmp_path: Path) -> None:
    """Contributes no unique lines; the only thing that would catch a real livekit API move."""
    pytest.importorskip("livekit")
    pytest.importorskip("livekit.agents")
    stream = _wav_input.WavFileAudioInput(_write_wav(tmp_path / "real.wav"))
    assert hasattr(stream, "wait_for_exhaustion")
    assert hasattr(stream, "aclose")
