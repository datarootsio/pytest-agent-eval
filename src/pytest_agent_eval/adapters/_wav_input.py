"""WAV file ``AudioInput`` for LiveKit voice sessions.

Streams a 16-bit mono PCM WAV at real-time pace, then keeps the session alive
by emitting silence frames so the Realtime model has time to finish responding
after the user audio drains.
"""

from __future__ import annotations

import asyncio
import wave
from pathlib import Path
from typing import Any


def _import_livekit() -> tuple[Any, Any]:
    """Return ``(rtc, AudioInput)`` from livekit, deferring the import.

    Kept out of module scope so importing :mod:`pytest_agent_eval` does not
    require ``livekit`` unless the user actually instantiates a
    :class:`WavFileAudioInput`.
    """
    from livekit import rtc
    from livekit.agents.voice.io import AudioInput

    return rtc, AudioInput


def _make_wav_file_audio_input_class() -> Any:
    rtc, AudioInput = _import_livekit()

    class WavFileAudioInput(AudioInput):
        """Replay a mono 16-bit PCM WAV in fixed-size frames at real-time pace."""

        def __init__(
            self,
            wav_path: Path,
            *,
            sample_rate: int = 24_000,
            frame_ms: int = 20,
        ) -> None:
            super().__init__(label=f"WavFileAudioInput({wav_path.name})")
            self._wav_path = wav_path
            self._sample_rate = sample_rate
            self._frame_ms = frame_ms
            self._samples_per_frame = sample_rate * frame_ms // 1000
            self._closed = False
            self._pcm: bytes = b""
            self._cursor = 0
            self._exhausted = asyncio.Event()

        def _load(self) -> None:
            with wave.open(str(self._wav_path), "rb") as wav:
                if wav.getnchannels() != 1:
                    raise ValueError(f"{self._wav_path}: expected mono, got {wav.getnchannels()} ch")
                if wav.getsampwidth() != 2:
                    raise ValueError(f"{self._wav_path}: expected 16-bit PCM, got {wav.getsampwidth() * 8}-bit")
                if wav.getframerate() != self._sample_rate:
                    raise ValueError(f"{self._wav_path}: expected {self._sample_rate} Hz, got {wav.getframerate()} Hz")
                self._pcm = wav.readframes(wav.getnframes())

        async def wait_for_exhaustion(self) -> None:
            """Block until the WAV has been fully streamed."""
            await self._exhausted.wait()

        async def __anext__(self) -> Any:
            if self._closed:
                raise StopAsyncIteration
            if not self._pcm:
                self._load()

            frame_bytes = self._samples_per_frame * 2
            chunk = self._pcm[self._cursor : self._cursor + frame_bytes]
            self._cursor += frame_bytes

            if len(chunk) < frame_bytes:
                chunk = chunk + b"\x00" * (frame_bytes - len(chunk))
                if not self._exhausted.is_set():
                    self._exhausted.set()

            await asyncio.sleep(self._frame_ms / 1000)

            return rtc.AudioFrame(
                data=chunk,
                sample_rate=self._sample_rate,
                num_channels=1,
                samples_per_channel=self._samples_per_frame,
            )

        async def aclose(self) -> None:
            """Stop streaming and release any waiters."""
            self._closed = True
            self._exhausted.set()

    return WavFileAudioInput


_class_cache: Any = None


def WavFileAudioInput(  # noqa: N802 — public name mirrors the class
    wav_path: Path,
    *,
    sample_rate: int = 24_000,
    frame_ms: int = 20,
) -> Any:
    """Construct a WAV-backed ``AudioInput`` (livekit imported lazily on first use)."""
    global _class_cache
    if _class_cache is None:
        _class_cache = _make_wav_file_audio_input_class()
    return _class_cache(wav_path, sample_rate=sample_rate, frame_ms=frame_ms)
