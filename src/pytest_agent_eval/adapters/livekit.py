"""LiveKit voice adapter — streams a WAV per turn into a fresh ``AgentSession``."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from pytest_agent_eval.adapters._wav_input import WavFileAudioInput

if TYPE_CHECKING:
    from livekit.agents.voice import Agent, AgentSession

logger = logging.getLogger(__name__)

SessionFactory = Callable[[], "tuple[AgentSession, Agent]"]


def _quiet_livekit_loggers() -> None:
    for name in ("livekit.agents", "livekit", "livekit.plugins.openai"):
        logging.getLogger(name).setLevel(logging.WARNING)


class LiveKitAdapter:
    """Voice adapter: streams a WAV per turn into a fresh LiveKit ``AgentSession``.

    The user supplies a ``session_factory`` callable that returns a fresh
    ``(AgentSession, Agent)`` pair on every invocation — one pair per turn.
    The adapter attaches a :class:`WavFileAudioInput` from the turn's
    ``audio:`` field, captures every executed tool call via
    ``function_tools_executed``, and accumulates the assistant transcript via
    ``conversation_item_added``.

    Args:
        session_factory: Returns a fresh ``(AgentSession, Agent)`` per call.
        sample_rate: WAV sample rate in Hz (must match the input file). Default
            24 kHz, the OpenAI Realtime native rate.
        frame_ms: Frame size in milliseconds. Default 20 ms.
        grace_period_s: Seconds to wait after the WAV drains before closing
            the session — gives the model time to fire trailing tool calls.
        timeout_s: Maximum seconds to wait for WAV exhaustion before forcibly
            closing the session.

    Example:
        ```python
        from livekit.agents.voice import Agent, AgentSession
        from livekit.plugins import openai
        from pytest_agent_eval.adapters.livekit import LiveKitAdapter

        def make_session():
            session = AgentSession(llm=openai.realtime.RealtimeModel())
            agent = Agent(instructions="...", tools=[...])
            return session, agent

        @pytest.fixture
        def llm_eval_agent():
            return LiveKitAdapter(make_session)
        ```
    """

    def __init__(
        self,
        session_factory: SessionFactory,
        *,
        sample_rate: int = 24_000,
        frame_ms: int = 20,
        grace_period_s: float = 8.0,
        timeout_s: float = 30.0,
    ) -> None:
        """Store the session factory and streaming/event-capture knobs."""
        self._session_factory = session_factory
        self._sample_rate = sample_rate
        self._frame_ms = frame_ms
        self._grace_period_s = grace_period_s
        self._timeout_s = timeout_s
        _quiet_livekit_loggers()

    async def __call__(self, history: list[dict[str, Any]]) -> tuple[str, list[str]]:
        """Stream the WAV on the last user turn and return ``(reply, tool_calls)``."""
        if not history or history[-1].get("role") != "user":
            raise ValueError("LiveKitAdapter: history must end with a user turn")
        audio_path_raw = history[-1].get("audio")
        if not audio_path_raw:
            raise ValueError(
                "LiveKitAdapter requires Turn.audio — the last user turn has no audio path. "
                "Run `python -m pytest_agent_eval.synthesize_audio` to generate fixtures."
            )

        wav_path = Path(audio_path_raw)
        if not wav_path.exists():
            raise FileNotFoundError(
                f"LiveKitAdapter: WAV fixture missing at {wav_path}. "
                "Run `python -m pytest_agent_eval.synthesize_audio` to generate it."
            )

        session, agent = self._session_factory()

        tool_calls: list[str] = []
        reply_chunks: list[str] = []

        def _on_function_tools_executed(event: Any) -> None:
            for fc in getattr(event, "function_calls", []) or []:
                name = getattr(fc, "name", "") or ""
                if name:
                    tool_calls.append(name)

        def _on_conversation_item_added(event: Any) -> None:
            item = getattr(event, "item", None)
            if item is None:
                return
            if getattr(item, "role", None) != "assistant":
                return
            text = getattr(item, "text_content", None)
            if not text:
                content = getattr(item, "content", None) or []
                text = "".join(c for c in content if isinstance(c, str))
            if text:
                reply_chunks.append(text)

        session.on("function_tools_executed", _on_function_tools_executed)
        session.on("conversation_item_added", _on_conversation_item_added)

        wav_input = WavFileAudioInput(
            wav_path,
            sample_rate=self._sample_rate,
            frame_ms=self._frame_ms,
        )
        session.input.audio = wav_input

        try:
            await session.start(agent)
            try:
                await asyncio.wait_for(wav_input.wait_for_exhaustion(), timeout=self._timeout_s)
            except asyncio.TimeoutError:
                logger.warning("LiveKitAdapter: timed out waiting for WAV exhaustion")
            await asyncio.sleep(self._grace_period_s)
        finally:
            try:
                await wav_input.aclose()
            except Exception:
                logger.debug("LiveKitAdapter: wav_input.aclose raised", exc_info=True)
            try:
                await session.aclose()
            except Exception:
                logger.debug("LiveKitAdapter: session.aclose raised", exc_info=True)

        return "".join(reply_chunks), tool_calls
