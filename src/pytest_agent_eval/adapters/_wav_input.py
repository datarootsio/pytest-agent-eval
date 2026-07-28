"""WAV file ``AudioInput`` for LiveKit voice sessions.

Streams a 16-bit mono PCM WAV at real-time pace, then keeps the session alive
by emitting silence frames so the Realtime model has time to finish responding
after the user audio drains.
"""

from __future__ import annotations

import asyncio
import functools
import wave
from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    from pathlib import Path

    from livekit.agents.voice.io import AudioInput as LiveKitAudioInput
    from livekit.rtc import AudioFrame as LiveKitAudioFrame

_PCM16_BYTES = 2


class _LiveKitTypes(NamedTuple):
    """The two livekit types a WAV-backed audio input is assembled from.

    A NamedTuple rather than the usual frozen dataclass: ruff treats dataclass
    annotations as runtime-evaluated, which would drag the livekit imports out of the
    ``TYPE_CHECKING`` block and make the module unimportable without the extra.
    """

    audio_frame: type[LiveKitAudioFrame]
    audio_input: type[LiveKitAudioInput]


def _import_livekit() -> _LiveKitTypes:
    """Return the livekit types the streamer needs, deferring the import.

    Kept out of module scope so importing :mod:`pytest_agent_eval` does not
    require ``livekit`` unless the user actually instantiates a
    :class:`WavFileAudioInput`.
    """
    try:
        # Deferred so the livekit extra stays optional: this module must import without it.
        from livekit import rtc  # noqa: PLC0415
        from livekit.agents.voice.io import AudioInput  # noqa: PLC0415
    except ImportError as exc:
        raise ImportError(
            "WavFileAudioInput requires the 'livekit' extra. Install with: pip install 'pytest-agent-eval[livekit]'"
        ) from exc

    return _LiveKitTypes(rtc.AudioFrame, AudioInput)


class _WavStreamer:
    """Replay a mono 16-bit PCM WAV in fixed-size frames at real-time pace.

    Inherits nothing on purpose: livekit's ``AudioInput`` base cannot be named until
    the extra is installed, so the whole of the streaming logic is typed here and the
    cached factory mixes this class into that base.
    """

    def __init__(
        self,
        wav_path: Path,
        *,
        sample_rate: int = 24_000,
        frame_ms: int = 20,
    ) -> None:
        """Store the WAV path and the frame geometry to replay it with."""
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
            if wav.getsampwidth() != _PCM16_BYTES:
                raise ValueError(f"{self._wav_path}: expected 16-bit PCM, got {wav.getsampwidth() * 8}-bit")
            if wav.getframerate() != self._sample_rate:
                raise ValueError(f"{self._wav_path}: expected {self._sample_rate} Hz, got {wav.getframerate()} Hz")
            self._pcm = wav.readframes(wav.getnframes())

    async def wait_for_exhaustion(self) -> None:
        """Block until the WAV has been fully streamed."""
        await self._exhausted.wait()

    async def next_chunk(self) -> bytes:
        """Return one frame of PCM, zero-padded and then silent once the WAV drains."""
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

        return chunk

    async def aclose(self) -> None:
        """Stop streaming and release any waiters."""
        self._closed = True
        self._exhausted.set()


@functools.cache
def _make_wav_file_audio_input_class() -> type[_WavStreamer]:
    """Build the livekit ``AudioInput`` subclass, importing livekit on the first call only."""
    livekit = _import_livekit()

    class _WavFileAudioInput(_WavStreamer, livekit.audio_input):  # ty: ignore[unsupported-base]
        """The WAV streamer, mixed into livekit's ``AudioInput`` base."""

        def __init__(
            self,
            wav_path: Path,
            *,
            sample_rate: int = 24_000,
            frame_ms: int = 20,
        ) -> None:
            """Label the input for livekit, then arm the WAV streamer."""
            livekit.audio_input.__init__(self, label=f"WavFileAudioInput({wav_path.name})")
            _WavStreamer.__init__(self, wav_path, sample_rate=sample_rate, frame_ms=frame_ms)

        async def __anext__(self) -> LiveKitAudioFrame:
            """Deliver the next PCM chunk as a livekit ``AudioFrame``."""
            return livekit.audio_frame(
                data=await self.next_chunk(),
                sample_rate=self._sample_rate,
                num_channels=1,
                samples_per_channel=self._samples_per_frame,
            )

    return _WavFileAudioInput


def WavFileAudioInput(  # noqa: N802 — public name mirrors the class
    wav_path: Path,
    *,
    sample_rate: int = 24_000,
    frame_ms: int = 20,
) -> _WavStreamer:
    """Construct a WAV-backed ``AudioInput`` (livekit imported lazily on first use)."""
    return _make_wav_file_audio_input_class()(wav_path, sample_rate=sample_rate, frame_ms=frame_ms)
