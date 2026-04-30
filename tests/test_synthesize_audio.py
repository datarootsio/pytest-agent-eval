"""Tests for ``python -m pytest_agent_eval.synthesize_audio`` (no real OpenAI calls)."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import pytest

from pytest_agent_eval import synthesize_audio as mod


def _make_yaml(path: Path, *, audio_name: str, user: str = "Hello") -> None:
    path.write_text(f"id: t\nturns:\n  - user: {user!r}\n    audio: {audio_name}\n")


@pytest.fixture
def fake_pcm_client(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Patch _build_client and _synth_pcm_via_realtime; return a counter."""
    state = {"calls": 0, "last_text": None, "last_voice": None, "last_model": None}

    class FakeClient:
        async def close(self) -> None:
            pass

    monkeypatch.setattr(mod, "_build_client", lambda: FakeClient())

    async def fake_synth(client: Any, *, text: str, voice: str, model: str) -> bytes:
        state["calls"] += 1
        state["last_text"] = text
        state["last_voice"] = voice
        state["last_model"] = model
        return b"\x00\x01" * 1000

    monkeypatch.setattr(mod, "_synth_pcm_via_realtime", fake_synth)
    monkeypatch.setattr(mod, "_INTER_TURN_DELAY_S", 0.0)
    return state


def _args(paths: list[str], *, force: bool = False) -> argparse.Namespace:
    return argparse.Namespace(
        paths=paths,
        force=force,
        voice="alloy",
        model="gpt-4o-realtime-preview",
    )


async def test_synth_writes_wav_and_hash(tmp_path: Path, fake_pcm_client: dict[str, Any]) -> None:
    yaml_path = tmp_path / "t.yaml"
    _make_yaml(yaml_path, audio_name="t.wav", user="Hi there")

    rc = await mod._run(_args([str(yaml_path)]))

    assert rc == 0
    assert (tmp_path / "t.wav").exists()
    assert (tmp_path / "t.wav.hash").exists()
    assert fake_pcm_client["calls"] == 1
    assert "Hi there" in fake_pcm_client["last_text"]


async def test_skips_when_hash_matches(tmp_path: Path, fake_pcm_client: dict[str, Any]) -> None:
    yaml_path = tmp_path / "t.yaml"
    _make_yaml(yaml_path, audio_name="t.wav", user="Hello")

    await mod._run(_args([str(yaml_path)]))
    assert fake_pcm_client["calls"] == 1

    await mod._run(_args([str(yaml_path)]))
    assert fake_pcm_client["calls"] == 1


async def test_resynth_when_user_text_changes(tmp_path: Path, fake_pcm_client: dict[str, Any]) -> None:
    yaml_path = tmp_path / "t.yaml"
    _make_yaml(yaml_path, audio_name="t.wav", user="Hello")
    await mod._run(_args([str(yaml_path)]))

    _make_yaml(yaml_path, audio_name="t.wav", user="Different now")
    await mod._run(_args([str(yaml_path)]))

    assert fake_pcm_client["calls"] == 2


async def test_force_ignores_cache(tmp_path: Path, fake_pcm_client: dict[str, Any]) -> None:
    yaml_path = tmp_path / "t.yaml"
    _make_yaml(yaml_path, audio_name="t.wav", user="Hello")
    await mod._run(_args([str(yaml_path)]))

    await mod._run(_args([str(yaml_path)], force=True))

    assert fake_pcm_client["calls"] == 2


async def test_writes_gitignore(tmp_path: Path, fake_pcm_client: dict[str, Any]) -> None:
    yaml_path = tmp_path / "t.yaml"
    _make_yaml(yaml_path, audio_name="t.wav")

    await mod._run(_args([str(yaml_path)]))

    gitignore = tmp_path / ".gitignore"
    assert gitignore.exists()
    text = gitignore.read_text()
    assert "*.wav" in text
    assert "*.wav.hash" in text


async def test_gitignore_idempotent(tmp_path: Path, fake_pcm_client: dict[str, Any]) -> None:
    yaml_path = tmp_path / "t.yaml"
    _make_yaml(yaml_path, audio_name="t.wav")
    (tmp_path / ".gitignore").write_text("# existing\nfoo.txt\n*.wav\n*.wav.hash\n")

    await mod._run(_args([str(yaml_path)]))

    text = (tmp_path / ".gitignore").read_text()
    assert text.count("*.wav\n") == 1
    assert text.count("*.wav.hash") == 1
    assert "foo.txt" in text


async def test_gitignore_appends_missing_entries(tmp_path: Path, fake_pcm_client: dict[str, Any]) -> None:
    yaml_path = tmp_path / "t.yaml"
    _make_yaml(yaml_path, audio_name="t.wav")
    (tmp_path / ".gitignore").write_text("foo.txt\n")

    await mod._run(_args([str(yaml_path)]))

    text = (tmp_path / ".gitignore").read_text()
    assert "foo.txt" in text
    assert "*.wav" in text
    assert "*.wav.hash" in text


async def test_accepts_directory(tmp_path: Path, fake_pcm_client: dict[str, Any]) -> None:
    eval_dir = tmp_path / "evals"
    eval_dir.mkdir()
    _make_yaml(eval_dir / "a.yaml", audio_name="a.wav", user="alpha")
    _make_yaml(eval_dir / "b.yaml", audio_name="b.wav", user="bravo")

    rc = await mod._run(_args([str(eval_dir)]))

    assert rc == 0
    assert (eval_dir / "a.wav").exists()
    assert (eval_dir / "b.wav").exists()
    assert fake_pcm_client["calls"] == 2


async def test_no_audio_field_skips_turn(tmp_path: Path, fake_pcm_client: dict[str, Any]) -> None:
    yaml_path = tmp_path / "t.yaml"
    yaml_path.write_text("id: t\nturns:\n  - user: hello\n")

    rc = await mod._run(_args([str(yaml_path)]))

    assert rc == 0
    assert fake_pcm_client["calls"] == 0


async def test_falls_back_to_pyproject_yaml_dirs(
    tmp_path: Path,
    fake_pcm_client: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    eval_dir = tmp_path / "tests" / "evals"
    eval_dir.mkdir(parents=True)
    _make_yaml(eval_dir / "a.yaml", audio_name="a.wav")
    (tmp_path / "pyproject.toml").write_text('[tool.agent_eval]\nyaml_dirs = ["tests/evals"]\n')

    monkeypatch.chdir(tmp_path)

    rc = await mod._run(_args([]))

    assert rc == 0
    assert (eval_dir / "a.wav").exists()


async def test_relative_audio_resolves_against_yaml_dir(tmp_path: Path, fake_pcm_client: dict[str, Any]) -> None:
    sub = tmp_path / "sub"
    sub.mkdir()
    _make_yaml(sub / "t.yaml", audio_name="audio/clip.wav")

    rc = await mod._run(_args([str(sub / "t.yaml")]))

    assert rc == 0
    assert (sub / "audio" / "clip.wav").exists()
    assert (sub / "audio" / "clip.wav.hash").exists()


def test_help_flag_exits_cleanly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["synthesize_audio", "--help"])
    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert exc.value.code == 0
