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
from pathlib import Path
from typing import Any

import yaml

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


def _transcript_hash(transcript: str) -> str:
    return hashlib.sha256(transcript.encode("utf-8")).hexdigest()


def _read_stored_hash(hash_path: Path) -> str | None:
    if not hash_path.exists():
        return None
    return hash_path.read_text().strip() or None


def _write_pcm_as_wav(pcm_bytes: bytes, out_path: Path) -> None:
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


def _iter_yaml_files(paths: list[Path]) -> list[Path]:
    out: list[Path] = []
    for p in paths:
        if p.is_dir():
            out.extend(sorted(p.rglob("*.yaml")))
            out.extend(sorted(p.rglob("*.yml")))
        elif p.suffix in (".yaml", ".yml"):
            out.append(p)
    return out


def _resolve_yaml_dirs_from_pyproject() -> list[Path]:
    pyproject = Path.cwd() / "pyproject.toml"
    if not pyproject.exists():
        return []
    with open(pyproject, "rb") as f:
        data = tomllib.load(f)
    section: dict[str, Any] = data.get("tool", {}).get("agent_eval", {})
    yaml_dirs = section.get("yaml_dirs", []) or []
    return [Path.cwd() / d for d in yaml_dirs]


def _load_turns(yaml_path: Path) -> list[tuple[str, Path]]:
    """Return ``(transcript_text, resolved_audio_path)`` for every turn with audio set."""
    raw = yaml.safe_load(yaml_path.read_text())
    if not isinstance(raw, dict):
        return []
    turns = raw.get("turns") or []
    yaml_dir = yaml_path.parent
    out: list[tuple[str, Path]] = []
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
        out.append((user.strip(), audio_path))
    return out


def _is_transient(exc: BaseException) -> bool:
    text = str(exc)
    if "HTTP 429" in text or "HTTP 5" in text:
        return True
    if "no audio" in text.lower():
        return True
    return False


async def _synth_pcm_via_realtime(
    client: Any,
    *,
    text: str,
    voice: str,
    model: str,
) -> bytes:
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


async def _synth_with_retry(
    client: Any,
    *,
    text: str,
    voice: str,
    model: str,
    label: str,
) -> bytes:
    last_exc: BaseException | None = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            return await _synth_pcm_via_realtime(client, text=text, voice=voice, model=model)
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
    raise last_exc  # type: ignore[misc]


def _build_client() -> Any:
    try:
        from openai import AsyncOpenAI
    except ImportError as exc:
        raise SystemExit(
            "ERROR: the 'openai' package is required. "
            "Install with: pip install 'pytest-agent-eval[livekit]' (or pip install openai)."
        ) from exc
    return AsyncOpenAI()


async def _process_one(
    *,
    transcript: str,
    audio_path: Path,
    force: bool,
    client: Any,
    voice: str,
    model: str,
) -> str:
    """Return ``"synthesised"``, ``"up-to-date"``, or ``"failed"``."""
    hash_path = audio_path.with_suffix(audio_path.suffix + ".hash")
    expected_hash = _transcript_hash(transcript)
    if not force and audio_path.exists() and _read_stored_hash(hash_path) == expected_hash:
        return "up-to-date"

    pcm = await _synth_with_retry(
        client,
        text=transcript,
        voice=voice,
        model=model,
        label=audio_path.name,
    )
    _write_pcm_as_wav(pcm, audio_path)
    hash_path.write_text(expected_hash + "\n")
    return "synthesised"


async def _run(args: argparse.Namespace) -> int:
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

    work: list[tuple[str, Path]] = []
    for yaml_path in yaml_files:
        work.extend(_load_turns(yaml_path))

    if not work:
        print("No turns with `audio:` declared — nothing to synthesise.")
        return 0

    needs_synth = []
    up_to_date = 0
    for transcript, audio_path in work:
        hash_path = audio_path.with_suffix(audio_path.suffix + ".hash")
        if not args.force and audio_path.exists() and _read_stored_hash(hash_path) == _transcript_hash(transcript):
            up_to_date += 1
        else:
            needs_synth.append((transcript, audio_path))

    client: Any = None
    if needs_synth:
        client = _build_client()

    synthesised = 0
    failed = 0
    written_dirs: set[Path] = set()
    try:
        for i, (transcript, audio_path) in enumerate(needs_synth):
            if i > 0:
                await asyncio.sleep(_INTER_TURN_DELAY_S)
            try:
                action = await _process_one(
                    transcript=transcript,
                    audio_path=audio_path,
                    force=args.force,
                    client=client,
                    voice=args.voice,
                    model=args.model,
                )
            except Exception as exc:
                print(f"FAIL  {audio_path}: {exc}", file=sys.stderr)
                failed += 1
                continue
            if action == "synthesised":
                synthesised += 1
                written_dirs.add(audio_path.parent)
            print(f"{action:<14} {audio_path}")
    finally:
        if client is not None:
            await client.close()

    gitignore_changed_dirs = sorted(d for d in written_dirs if _ensure_gitignore(d))

    summary = f"Synthesized {synthesised} new WAVs, {up_to_date} already up to date."
    if failed:
        summary += f" {failed} failed."
    print(f"\n{summary}")
    if gitignore_changed_dirs:
        dirs_str = ", ".join(str(d) for d in gitignore_changed_dirs)
        print(
            f"Wrote .gitignore in {dirs_str} ({', '.join(_GITIGNORE_ENTRIES)}) — generated audio is local-only;\n"
            "commit YAML transcripts only."
        )

    return 0 if failed == 0 else 2


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
    args = parser.parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())
