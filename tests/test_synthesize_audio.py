"""Tests for ``python -m pytest_agent_eval.synthesize_audio`` (no real OpenAI calls)."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from pytest_agent_eval import synthesize_audio as mod


def _make_yaml(path: Path, *, audio_name: str, user: str = "Hello") -> None:
    path.write_text(f"id: t\nturns:\n  - user: {user!r}\n    audio: {audio_name}\n")


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


@pytest.fixture
def synth_spy(monkeypatch: pytest.MonkeyPatch) -> SynthSpy:
    """A SynthSpy with the inter-turn delay removed so tests do not sleep."""
    monkeypatch.setattr(mod, "_INTER_TURN_DELAY_S", 0.0)
    return SynthSpy()


async def _run_with(spy: SynthSpy, args: argparse.Namespace) -> int:
    return await mod._run(args, synth=spy, client_factory=spy.client_factory)


def _args(paths: list[str], *, force: bool = False) -> argparse.Namespace:
    return argparse.Namespace(
        paths=paths,
        force=force,
        voice="alloy",
        model="gpt-4o-realtime-preview",
    )


async def test_synth_writes_wav_and_hash(tmp_path: Path, synth_spy: SynthSpy) -> None:
    yaml_path = tmp_path / "t.yaml"
    _make_yaml(yaml_path, audio_name="t.wav", user="Hi there")

    rc = await _run_with(synth_spy, _args([str(yaml_path)]))

    assert rc == 0
    assert (tmp_path / "t.wav").exists()
    assert (tmp_path / "t.wav.hash").exists()
    assert synth_spy.count == 1
    assert "Hi there" in synth_spy.calls[-1].text


async def test_skips_when_hash_matches(tmp_path: Path, synth_spy: SynthSpy) -> None:
    yaml_path = tmp_path / "t.yaml"
    _make_yaml(yaml_path, audio_name="t.wav", user="Hello")

    await _run_with(synth_spy, _args([str(yaml_path)]))
    assert synth_spy.count == 1

    await _run_with(synth_spy, _args([str(yaml_path)]))
    assert synth_spy.count == 1


async def test_resynth_when_user_text_changes(tmp_path: Path, synth_spy: SynthSpy) -> None:
    yaml_path = tmp_path / "t.yaml"
    _make_yaml(yaml_path, audio_name="t.wav", user="Hello")
    await _run_with(synth_spy, _args([str(yaml_path)]))

    _make_yaml(yaml_path, audio_name="t.wav", user="Different now")
    await _run_with(synth_spy, _args([str(yaml_path)]))

    assert synth_spy.count == 2


async def test_force_ignores_cache(tmp_path: Path, synth_spy: SynthSpy) -> None:
    yaml_path = tmp_path / "t.yaml"
    _make_yaml(yaml_path, audio_name="t.wav", user="Hello")
    await _run_with(synth_spy, _args([str(yaml_path)]))

    await _run_with(synth_spy, _args([str(yaml_path)], force=True))

    assert synth_spy.count == 2


async def test_writes_gitignore(tmp_path: Path, synth_spy: SynthSpy) -> None:
    yaml_path = tmp_path / "t.yaml"
    _make_yaml(yaml_path, audio_name="t.wav")

    await _run_with(synth_spy, _args([str(yaml_path)]))

    gitignore = tmp_path / ".gitignore"
    assert gitignore.exists()
    text = gitignore.read_text()
    assert "*.wav" in text
    assert "*.wav.hash" in text


async def test_gitignore_idempotent(tmp_path: Path, synth_spy: SynthSpy) -> None:
    yaml_path = tmp_path / "t.yaml"
    _make_yaml(yaml_path, audio_name="t.wav")
    (tmp_path / ".gitignore").write_text("# existing\nfoo.txt\n*.wav\n*.wav.hash\n")

    await _run_with(synth_spy, _args([str(yaml_path)]))

    text = (tmp_path / ".gitignore").read_text()
    assert text.count("*.wav\n") == 1
    assert text.count("*.wav.hash") == 1
    assert "foo.txt" in text


async def test_gitignore_appends_missing_entries(tmp_path: Path, synth_spy: SynthSpy) -> None:
    yaml_path = tmp_path / "t.yaml"
    _make_yaml(yaml_path, audio_name="t.wav")
    (tmp_path / ".gitignore").write_text("foo.txt\n")

    await _run_with(synth_spy, _args([str(yaml_path)]))

    text = (tmp_path / ".gitignore").read_text()
    assert "foo.txt" in text
    assert "*.wav" in text
    assert "*.wav.hash" in text


async def test_accepts_directory(tmp_path: Path, synth_spy: SynthSpy) -> None:
    eval_dir = tmp_path / "evals"
    eval_dir.mkdir()
    _make_yaml(eval_dir / "a.yaml", audio_name="a.wav", user="alpha")
    _make_yaml(eval_dir / "b.yaml", audio_name="b.wav", user="bravo")

    rc = await _run_with(synth_spy, _args([str(eval_dir)]))

    assert rc == 0
    assert (eval_dir / "a.wav").exists()
    assert (eval_dir / "b.wav").exists()
    assert synth_spy.count == 2


async def test_no_audio_field_skips_turn(tmp_path: Path, synth_spy: SynthSpy) -> None:
    yaml_path = tmp_path / "t.yaml"
    yaml_path.write_text("id: t\nturns:\n  - user: hello\n")

    rc = await _run_with(synth_spy, _args([str(yaml_path)]))

    assert rc == 0
    assert synth_spy.count == 0


async def test_falls_back_to_pyproject_yaml_dirs(
    tmp_path: Path,
    synth_spy: SynthSpy,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    eval_dir = tmp_path / "tests" / "evals"
    eval_dir.mkdir(parents=True)
    _make_yaml(eval_dir / "a.yaml", audio_name="a.wav")
    (tmp_path / "pyproject.toml").write_text('[tool.agent_eval]\nyaml_dirs = ["tests/evals"]\n')

    monkeypatch.chdir(tmp_path)

    rc = await _run_with(synth_spy, _args([]))

    assert rc == 0
    assert (eval_dir / "a.wav").exists()


async def test_relative_audio_resolves_against_yaml_dir(tmp_path: Path, synth_spy: SynthSpy) -> None:
    sub = tmp_path / "sub"
    sub.mkdir()
    _make_yaml(sub / "t.yaml", audio_name="audio/clip.wav")

    rc = await _run_with(synth_spy, _args([str(sub / "t.yaml")]))

    assert rc == 0
    assert (sub / "audio" / "clip.wav").exists()
    assert (sub / "audio" / "clip.wav.hash").exists()


def test_help_flag_exits_cleanly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["synthesize_audio", "--help"])
    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert exc.value.code == 0
