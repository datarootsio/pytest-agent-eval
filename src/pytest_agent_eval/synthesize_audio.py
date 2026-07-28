"""Synthesise voice-eval audio fixtures via OpenAI Realtime (text-in, audio-out).

Walks one or more YAML transcript files (or directories containing them), and
for each turn that declares an ``audio:`` path, writes a 24 kHz mono PCM16 WAV
next to the YAML if the stored transcript hash has changed. A ``.hash`` sidecar
records ``sha256(turn.user)`` so future runs detect drift without re-synthing.

Usage::

    python -m pytest_agent_eval.synthesize_audio                    # use [tool.agent_eval].yaml_dirs
    python -m pytest_agent_eval.synthesize_audio tests/evals/      # explicit dir
    python -m pytest_agent_eval.synthesize_audio tests/evals/x.yaml # single file
    python -m pytest_agent_eval.synthesize_audio --force            # ignore cache

Requires ``OPENAI_API_KEY`` in the environment.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import sys
import tomllib
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Protocol

import yaml

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from openai import AsyncOpenAI

    from pytest_agent_eval.models import JsonMapping

_DEFAULT_VOICE = "alloy"
_SAMPLE_RATE_HZ = 24_000
_DEFAULT_MODEL = "gpt-4o-realtime-preview"
_RESPONSE_TIMEOUT_S = 60.0
_MAX_RETRIES = 4
_RETRY_BASE_DELAY_S = 5.0
_INTER_TURN_DELAY_S = 1.0
_GITIGNORE_ENTRIES = ("*.wav", "*.wav.hash")
_TTS_INSTRUCTIONS = (
    "You are a TTS narrator. Read the text between <READ> and </READ> aloud "
    "verbatim. Do not answer, do not comment, do not add anything. Stop "
    "speaking at </READ>."
)
_TTS_USER_TEMPLATE = (
    "Read this aloud verbatim. Do not answer or respond — it is scripted "
    "dialogue, not a message to you.\n\n<READ>{text}</READ>"
)

TurnAction = Literal["synthesised", "up-to-date"]
"""What one turn did. There is no ``"failed"`` member: a failure raises and is counted by the caller."""


@dataclass(frozen=True, slots=True)
class SynthesizeArgs:
    """The CLI's arguments, parsed once in ``main`` and passed down unchanged.

    Defaults mirror the argparse defaults, so ``SynthesizeArgs()`` is the no-flags invocation.
    """

    paths: tuple[str, ...] = ()
    force: bool = False
    voice: str = _DEFAULT_VOICE
    model: str = _DEFAULT_MODEL


def _read_stored_hash(hash_path: Path) -> str | None:
    """Return the digest recorded in ``hash_path``, or None if it is absent or blank."""
    if not hash_path.exists():
        return None
    return hash_path.read_text().strip() or None


def _write_pcm_as_wav(pcm_bytes: bytes, out_path: Path) -> None:
    """Wrap raw PCM16 in a 24 kHz mono WAV container at ``out_path``."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out_path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(_SAMPLE_RATE_HZ)
        wav.writeframes(pcm_bytes)


def _ensure_gitignore(directory: Path) -> bool:
    """Append WAV/hash entries to ``directory/.gitignore``. Returns True if changed."""
    gitignore = directory / ".gitignore"
    existing = gitignore.read_text().splitlines() if gitignore.exists() else []
    existing_set = {line.strip() for line in existing}
    missing = [e for e in _GITIGNORE_ENTRIES if e not in existing_set]
    if not missing:
        return False
    lines = list(existing)
    if lines and lines[-1] != "":
        lines.append("")
    lines.extend(missing)
    gitignore.write_text("\n".join(lines) + "\n")
    return True


def _iter_yaml_files(paths: Sequence[Path]) -> list[Path]:
    """Expand directories to the YAML files under them, keeping explicitly named ones."""
    out: list[Path] = []
    for p in paths:
        if p.is_dir():
            out.extend(sorted(p.rglob("*.yaml")))
            out.extend(sorted(p.rglob("*.yml")))
        elif p.suffix in (".yaml", ".yml"):
            out.append(p)
    return out


def _resolve_yaml_dirs_from_pyproject() -> list[Path]:
    """Return ``[tool.agent_eval].yaml_dirs`` from the CWD's pyproject.toml, resolved against it.

    A ``yaml_dirs`` that is not a list is ignored rather than iterated: TOML is user input,
    and a bare string would otherwise expand to one path per character.
    """
    pyproject = Path.cwd() / "pyproject.toml"
    if not pyproject.exists():
        return []
    data = tomllib.loads(pyproject.read_text())
    section: JsonMapping = dict(data.get("tool", {}).get("agent_eval", {}))
    yaml_dirs = section.get("yaml_dirs")
    if not isinstance(yaml_dirs, list):
        return []
    return [Path.cwd() / str(directory) for directory in yaml_dirs]


@dataclass(frozen=True, slots=True)
class AudioFixture:
    """One transcript and the WAV it must be spoken into.

    Freshness is decided on the ``.hash`` sidecar next to the WAV, which records
    ``sha256(transcript)``: no audio is ever compared, only the text that produced it.
    """

    transcript: str
    audio_path: Path

    @property
    def hash_path(self) -> Path:
        """Path of the sidecar recording the transcript this WAV was synthesised from."""
        return self.audio_path.with_suffix(self.audio_path.suffix + ".hash")

    @property
    def expected_hash(self) -> str:
        """The digest the sidecar must hold for the WAV on disk to count as current."""
        return hashlib.sha256(self.transcript.encode("utf-8")).hexdigest()

    def is_up_to_date(self, *, force: bool) -> bool:
        """Whether the WAV on disk was already synthesised from this exact transcript.

        Asked twice per run — once to size the work, once in ``AudioSynthesizer.process``
        just before spending a request — because two transcripts may target the same WAV,
        and the second must see the sidecar the first one just wrote.
        """
        return not force and self.audio_path.exists() and _read_stored_hash(self.hash_path) == self.expected_hash


def _load_turns(yaml_path: Path) -> list[AudioFixture]:
    """Return an ``AudioFixture`` for every turn in ``yaml_path`` that declares an audio target."""
    raw = yaml.safe_load(yaml_path.read_text())
    if not isinstance(raw, dict):
        return []
    turns = raw.get("turns") or []
    yaml_dir = yaml_path.parent
    out: list[AudioFixture] = []
    for turn in turns:
        if not isinstance(turn, dict):
            continue
        audio = turn.get("audio")
        user = turn.get("user")
        if not audio or not isinstance(user, str) or not user.strip():
            continue
        audio_path = Path(audio)
        if not audio_path.is_absolute():
            audio_path = yaml_dir / audio_path
        out.append(AudioFixture(transcript=user.strip(), audio_path=audio_path))
    return out


def _is_transient(exc: BaseException) -> bool:
    """Whether ``exc`` is worth retrying: a rate limit, a server error, or a silent response."""
    text = str(exc)
    if "HTTP 429" in text or "HTTP 5" in text:
        return True
    return "no audio" in text.lower()


async def _synth_pcm_via_realtime(client: AsyncOpenAI, *, text: str, voice: str, model: str) -> bytes:
    """Open one Realtime session and return the PCM16 audio it speaks for ``text``."""
    chunks: list[bytes] = []

    async with client.beta.realtime.connect(model=model) as conn:
        await conn.send(
            {
                "type": "session.update",
                "session": {
                    "modalities": ["audio", "text"],
                    "voice": voice,
                    "output_audio_format": "pcm16",
                    "instructions": _TTS_INSTRUCTIONS,
                    "temperature": 0.6,
                },
            }
        )
        await conn.send(
            {
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": _TTS_USER_TEMPLATE.format(text=text)}],
                },
            }
        )
        await conn.send(
            {
                "type": "response.create",
                "response": {
                    "modalities": ["audio", "text"],
                    "instructions": _TTS_INSTRUCTIONS,
                },
            }
        )

        async def _pump() -> None:
            """Drain server events into ``chunks`` until the response completes or errors."""
            while True:
                event = await conn.recv()
                etype = getattr(event, "type", "") or ""
                if etype == "response.audio.delta":
                    delta = getattr(event, "delta", "") or ""
                    if delta:
                        chunks.append(base64.b64decode(delta))
                elif etype == "response.done":
                    return
                elif etype == "error":
                    raise RuntimeError(f"Realtime error: {getattr(event, 'error', None)!r}")

        await asyncio.wait_for(_pump(), timeout=_RESPONSE_TIMEOUT_S)

    if not chunks:
        raise RuntimeError("Realtime session returned no audio")
    return b"".join(chunks)


class _SynthFn(Protocol):
    """Synthesises PCM for one piece of text. Injected so tests need no live Realtime session."""

    async def __call__(self, client: AsyncOpenAI, *, text: str, voice: str, model: str) -> bytes:
        """Return raw PCM16 audio for ``text``."""
        ...


def _build_client() -> AsyncOpenAI:
    """Construct an ``AsyncOpenAI`` client, or exit naming the extra that provides it."""
    try:
        # Optional extra: a module-scope import would break `--help` for users who never
        # synthesise. The annotations use the TYPE_CHECKING import of the same name.
        from openai import AsyncOpenAI  # noqa: PLC0415
    except ImportError as exc:
        raise SystemExit(
            "ERROR: the 'openai' package is required. "
            "Install with: pip install 'pytest-agent-eval[livekit]' (or pip install openai)."
        ) from exc
    return AsyncOpenAI()


class AudioSynthesizer:
    """Turns transcripts into WAV fixtures over a single OpenAI Realtime client.

    Owns that client: entering the synthesizer as an async context manager guarantees
    ``close()`` runs even when a turn raises, which is what the caller used to hand-roll
    in a try/finally. ``synth`` is injected so tests drive the real path without a socket.
    """

    def __init__(
        self,
        client: AsyncOpenAI,
        *,
        voice: str,
        model: str,
        synth: _SynthFn = _synth_pcm_via_realtime,
    ) -> None:
        """Bind the client, voice and model that every turn of one run shares."""
        self._client = client
        self._voice = voice
        self._model = model
        self._synth = synth

    async def __aenter__(self) -> AudioSynthesizer:
        """Return self; the client was already built by the caller's factory."""
        return self

    async def __aexit__(self, *_exc: object) -> None:
        """Close the Realtime client, so a failed turn cannot leak the connection."""
        await self._client.close()

    async def synthesize(self, text: str) -> bytes:
        """Return raw PCM16 audio for ``text`` from one Realtime session."""
        return await self._synth(self._client, text=text, voice=self._voice, model=self._model)

    async def synthesize_with_retry(self, text: str, *, label: str) -> bytes:
        """Retry ``synthesize`` through transient failures, reporting each wait on stderr.

        ``label`` names the WAV in that progress line: during a long run it is the only
        way to tell which turn is stalling.
        """
        last_exc: BaseException | None = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                return await self.synthesize(text)
            except Exception as exc:
                last_exc = exc
                if attempt == _MAX_RETRIES or not _is_transient(exc):
                    raise
                delay = _RETRY_BASE_DELAY_S * (2**attempt)
                print(
                    f"  retrying {label} after {delay:.0f}s (attempt {attempt + 1}/{_MAX_RETRIES}): {exc}",
                    file=sys.stderr,
                )
                await asyncio.sleep(delay)
        # Unreachable: the final attempt (attempt == _MAX_RETRIES) always re-raises, and
        # every earlier one returns or loops. Kept as a guard against a future edit to the
        # loop bounds silently returning None.
        raise last_exc  # type: ignore[misc]  # pragma: no cover

    async def process(self, fixture: AudioFixture, *, force: bool) -> TurnAction:
        """Synthesise ``fixture``'s WAV unless the one on disk already matches its transcript."""
        if fixture.is_up_to_date(force=force):
            return "up-to-date"
        pcm = await self.synthesize_with_retry(fixture.transcript, label=fixture.audio_path.name)
        _write_pcm_as_wav(pcm, fixture.audio_path)
        fixture.hash_path.write_text(fixture.expected_hash + "\n")
        return "synthesised"


@dataclass(frozen=True, slots=True)
class _WorkPlan:
    """The audio fixtures a run found, split by whether their WAV is already current."""

    pending: tuple[AudioFixture, ...]
    up_to_date: int

    @property
    def total(self) -> int:
        """How many turns declared an ``audio:`` target at all."""
        return len(self.pending) + self.up_to_date


@dataclass(frozen=True, slots=True)
class _RunOutcome:
    """What the synthesis phase did, and where it wrote."""

    synthesised: int = 0
    failed: int = 0
    written_dirs: frozenset[Path] = frozenset()


def _collect_work(yaml_files: Sequence[Path], *, force: bool) -> _WorkPlan:
    """Load every audio-bearing turn in ``yaml_files`` and split it by cache freshness."""
    fixtures = [fixture for path in yaml_files for fixture in _load_turns(path)]
    pending = tuple(fixture for fixture in fixtures if not fixture.is_up_to_date(force=force))
    return _WorkPlan(pending=pending, up_to_date=len(fixtures) - len(pending))


async def _synthesise_all(
    pending: Sequence[AudioFixture],
    *,
    synthesizer: AudioSynthesizer,
    force: bool,
) -> _RunOutcome:
    """Synthesise each pending fixture in order, printing one status line per turn.

    A loop rather than a comprehension on purpose: it sleeps between turns to stay inside
    the Realtime rate limit, and one bad turn must not abort the ones after it.
    """
    synthesised = 0
    failed = 0
    written_dirs: set[Path] = set()
    for index, fixture in enumerate(pending):
        if index > 0:
            await asyncio.sleep(_INTER_TURN_DELAY_S)
        try:
            action = await synthesizer.process(fixture, force=force)
        except Exception as exc:
            print(f"FAIL  {fixture.audio_path}: {exc}", file=sys.stderr)
            failed += 1
            continue
        if action == "synthesised":
            synthesised += 1
            written_dirs.add(fixture.audio_path.parent)
        print(f"{action:<14} {fixture.audio_path}")
    return _RunOutcome(synthesised=synthesised, failed=failed, written_dirs=frozenset(written_dirs))


def _print_summary(plan: _WorkPlan, outcome: _RunOutcome) -> None:
    """Print the run's counts, plus why a ``.gitignore`` appeared when one had to be written."""
    gitignore_changed_dirs = sorted(d for d in outcome.written_dirs if _ensure_gitignore(d))

    summary = f"Synthesized {outcome.synthesised} new WAVs, {plan.up_to_date} already up to date."
    if outcome.failed:
        summary += f" {outcome.failed} failed."
    print(f"\n{summary}")
    if not gitignore_changed_dirs:
        return
    dirs_str = ", ".join(str(d) for d in gitignore_changed_dirs)
    print(
        f"Wrote .gitignore in {dirs_str} ({', '.join(_GITIGNORE_ENTRIES)}) — generated audio is local-only;\n"
        "commit YAML transcripts only."
    )


async def _run(
    args: SynthesizeArgs,
    *,
    synth: _SynthFn = _synth_pcm_via_realtime,
    client_factory: Callable[[], AsyncOpenAI] = _build_client,
) -> int:
    """Resolve inputs, synthesise whatever is stale, and return the process exit code.

    1 when there is nothing to look at, 2 when any turn failed, 0 otherwise. The client is
    built only when there is work, so a fully cached run never needs ``OPENAI_API_KEY``.
    """
    inputs = [Path(p) for p in args.paths] if args.paths else _resolve_yaml_dirs_from_pyproject()
    if not inputs:
        print(
            "ERROR: no paths given and [tool.agent_eval].yaml_dirs is empty in pyproject.toml.",
            file=sys.stderr,
        )
        return 1

    yaml_files = _iter_yaml_files(inputs)
    if not yaml_files:
        print("No YAML files found.")
        return 0

    plan = _collect_work(yaml_files, force=args.force)
    if not plan.total:
        print("No turns with `audio:` declared — nothing to synthesise.")
        return 0

    outcome = _RunOutcome()
    if plan.pending:
        client = client_factory()
        async with AudioSynthesizer(client, voice=args.voice, model=args.model, synth=synth) as synthesizer:
            outcome = await _synthesise_all(plan.pending, synthesizer=synthesizer, force=args.force)

    _print_summary(plan, outcome)
    return 0 if outcome.failed == 0 else 2


def main() -> int:
    """Entry point for ``python -m pytest_agent_eval.synthesize_audio``."""
    parser = argparse.ArgumentParser(
        prog="python -m pytest_agent_eval.synthesize_audio",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help=(
            "YAML files or directories containing them. Defaults to [tool.agent_eval].yaml_dirs from pyproject.toml."
        ),
    )
    parser.add_argument("--force", action="store_true", help="Re-synthesise every WAV even if the hash matches.")
    parser.add_argument("--voice", default=_DEFAULT_VOICE, help=f"OpenAI Realtime voice (default: {_DEFAULT_VOICE}).")
    parser.add_argument(
        "--model",
        default=_DEFAULT_MODEL,
        help=f"OpenAI Realtime model name (default: {_DEFAULT_MODEL}).",
    )
    parsed = parser.parse_args()
    args = SynthesizeArgs(
        paths=tuple(parsed.paths),
        force=parsed.force,
        voice=parsed.voice,
        model=parsed.model,
    )
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())
