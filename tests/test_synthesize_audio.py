"""Tests for ``python -m pytest_agent_eval.synthesize_audio`` (no real OpenAI calls)."""

from __future__ import annotations

import base64
import hashlib
import sys
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest

from pytest_agent_eval import synthesize_audio as mod
from tests.helpers.spies import SynthSpy

if TYPE_CHECKING:
    from pathlib import Path


def _make_yaml(path: Path, *, audio_name: str, user: str = "Hello") -> None:
    path.write_text(f"id: t\nturns:\n  - user: {user!r}\n    audio: {audio_name}\n")


@pytest.fixture
def synth_spy(monkeypatch: pytest.MonkeyPatch) -> SynthSpy:
    """A SynthSpy with the inter-turn delay removed so tests do not sleep."""
    monkeypatch.setattr(mod, "_INTER_TURN_DELAY_S", 0.0)
    return SynthSpy()


async def _run_with(spy: SynthSpy, args: mod.SynthesizeArgs) -> int:
    return await mod._run(args, synth=spy, client_factory=spy.client_factory)


def _args(paths: list[str], *, force: bool = False) -> mod.SynthesizeArgs:
    return mod.SynthesizeArgs(
        paths=tuple(paths),
        force=force,
        voice="alloy",
        model="gpt-4o-realtime-preview",
    )


def _synthesizer(spy: SynthSpy, *, voice: str = "v", model: str = "m") -> mod.AudioSynthesizer:
    """An AudioSynthesizer driven by a spy, which ignores the client it is handed.

    The spy's own fake client rather than None: the parameter is the real ``AsyncOpenAI``
    now, and widening it to ``| None`` to let a test pass one would put a branch in
    ``__aexit__`` that only tests reach.
    """
    return mod.AudioSynthesizer(spy.client_factory(), voice=voice, model=model, synth=spy)


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


# --- YAML scanning edge cases ---


def test_load_turns_ignores_a_non_mapping_document(tmp_path: Path) -> None:
    """A YAML list where a transcript was expected is skipped, not crashed on."""
    path = tmp_path / "list.yaml"
    path.write_text("- not\n- a\n- transcript\n")
    assert mod._load_turns(path) == []


def test_load_turns_skips_non_mapping_turns(tmp_path: Path) -> None:
    path = tmp_path / "t.yaml"
    path.write_text("id: t\nturns:\n  - just a string\n  - user: real\n    audio: r.wav\n")
    assert [fixture.transcript for fixture in mod._load_turns(path)] == ["real"]


def test_read_stored_hash_returns_none_for_an_empty_sidecar(tmp_path: Path) -> None:
    """A truncated .hash file must read as 'no hash', forcing a re-synth."""
    sidecar = tmp_path / "t.wav.hash"
    sidecar.write_text("   \n")
    assert mod._read_stored_hash(sidecar) is None
    assert mod._read_stored_hash(tmp_path / "absent.hash") is None


def test_resolve_yaml_dirs_returns_empty_without_a_pyproject(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert mod._resolve_yaml_dirs_from_pyproject() == []


def test_resolve_yaml_dirs_ignores_a_non_list_setting(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A bare string would otherwise expand to one path per character."""
    (tmp_path / "pyproject.toml").write_text('[tool.agent_eval]\nyaml_dirs = "tests/evals"\n')
    monkeypatch.chdir(tmp_path)
    assert mod._resolve_yaml_dirs_from_pyproject() == []


# --- transient-failure classification ---


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("HTTP 429 Too Many Requests", True),
        ("HTTP 503 Service Unavailable", True),
        ("Realtime session returned no audio", True),
        ("NO AUDIO returned", True),
        ("HTTP 400 Bad Request", False),
        ("invalid api key", False),
    ],
    ids=["rate_limit", "server_error", "no_audio", "no_audio_uppercase", "bad_request", "auth"],
)
def test_is_transient_classification(message: str, expected: bool) -> None:
    """Only rate limits, server errors and empty audio are worth retrying."""
    assert mod._is_transient(RuntimeError(message)) is expected


# --- the Realtime session ---


class _FakeConn:
    """Scripted Realtime connection: records sends, replays a fixed event stream."""

    def __init__(self, events: list[Any]) -> None:
        self.sent: list[dict[str, Any]] = []
        self._events = list(events)

    async def send(self, payload: dict[str, Any]) -> None:
        self.sent.append(payload)

    async def recv(self) -> Any:
        if not self._events:
            raise AssertionError("Realtime pump asked for more events than the script provides")
        return self._events.pop(0)


class _FakeRealtimeClient:
    """Minimal stand-in for AsyncOpenAI's beta.realtime surface."""

    def __init__(self, events: list[Any]) -> None:
        self.conn = _FakeConn(events)
        self.connected_model: str | None = None
        outer = self

        class _Connect:
            def __call__(self, *, model: str) -> Any:
                outer.connected_model = model
                return self

            async def __aenter__(self) -> _FakeConn:
                return outer.conn

            async def __aexit__(self, *_exc: Any) -> None:
                return None

        self.beta = SimpleNamespace(realtime=SimpleNamespace(connect=_Connect()))


def _event(etype: str, **kwargs: Any) -> Any:
    return SimpleNamespace(type=etype, **kwargs)


def _audio_delta(pcm: bytes) -> Any:
    return _event("response.audio.delta", delta=base64.b64encode(pcm).decode())


async def test_realtime_session_concatenates_audio_deltas() -> None:
    client = _FakeRealtimeClient([_audio_delta(b"\x01\x02"), _audio_delta(b"\x03\x04"), _event("response.done")])

    pcm = await mod._synth_pcm_via_realtime(client, text="Book me a slot", voice="echo", model="realtime-x")

    assert pcm == b"\x01\x02\x03\x04"
    assert client.connected_model == "realtime-x"


async def test_realtime_session_configures_voice_and_pcm16() -> None:
    client = _FakeRealtimeClient([_audio_delta(b"\x01"), _event("response.done")])

    await mod._synth_pcm_via_realtime(client, text="Hello there", voice="echo", model="m")

    update, create, respond = client.conn.sent
    assert update["session"]["voice"] == "echo"
    assert update["session"]["output_audio_format"] == "pcm16"
    assert update["session"]["modalities"] == ["audio", "text"]
    # The text must be wrapped in the read-verbatim template, or the model answers it.
    prompt = create["item"]["content"][0]["text"]
    assert "<READ>Hello there</READ>" in prompt
    assert respond["type"] == "response.create"


async def test_realtime_session_ignores_empty_deltas_and_unknown_events() -> None:
    client = _FakeRealtimeClient(
        [
            _event("response.text.delta", delta="ignored"),
            _event("response.audio.delta", delta=""),
            _audio_delta(b"\xaa"),
            _event("response.done"),
        ]
    )

    assert await mod._synth_pcm_via_realtime(client, text="t", voice="v", model="m") == b"\xaa"


async def test_realtime_error_event_is_surfaced() -> None:
    client = _FakeRealtimeClient([_event("error", error={"code": "invalid_voice"})])

    with pytest.raises(RuntimeError, match="Realtime error:.*invalid_voice"):
        await mod._synth_pcm_via_realtime(client, text="t", voice="nope", model="m")


async def test_realtime_session_without_audio_is_an_error() -> None:
    """A silent response must fail loudly rather than write a 0-byte WAV."""
    client = _FakeRealtimeClient([_event("response.done")])

    with pytest.raises(RuntimeError, match="Realtime session returned no audio"):
        await mod._synth_pcm_via_realtime(client, text="t", voice="v", model="m")


# --- retry behaviour ---


@pytest.fixture
def no_retry_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mod, "_RETRY_BASE_DELAY_S", 0.0)


async def test_retries_a_transient_failure_then_succeeds(no_retry_delay: None) -> None:
    spy = SynthSpy(fail_with=RuntimeError("HTTP 429 slow down"), fail_times=2)

    pcm = await _synthesizer(spy).synthesize_with_retry("t", label="t.wav")

    assert pcm
    assert spy.count == 3


async def test_does_not_retry_a_non_transient_failure(no_retry_delay: None) -> None:
    """Retrying a 400 or an auth error just burns quota."""
    spy = SynthSpy(fail_with=RuntimeError("HTTP 400 Bad Request"))

    with pytest.raises(RuntimeError, match="HTTP 400"):
        await _synthesizer(spy).synthesize_with_retry("t", label="t.wav")

    assert spy.count == 1


async def test_gives_up_after_max_retries(no_retry_delay: None) -> None:
    spy = SynthSpy(fail_with=RuntimeError("HTTP 500 boom"))

    with pytest.raises(RuntimeError, match="HTTP 500"):
        await _synthesizer(spy).synthesize_with_retry("t", label="t.wav")

    assert spy.count == mod._MAX_RETRIES + 1


async def test_retry_progress_is_reported_on_stderr(no_retry_delay: None, capsys: pytest.CaptureFixture[str]) -> None:
    spy = SynthSpy(fail_with=RuntimeError("HTTP 429 slow down"), fail_times=1)

    await _synthesizer(spy).synthesize_with_retry("t", label="turn1.wav")

    assert "retrying turn1.wav" in capsys.readouterr().err


# --- client construction ---


def test_build_client_returns_an_async_openai_client(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("openai")
    from openai import AsyncOpenAI

    # A key must be present for the constructor to run; no request is ever made.
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-a-real-key")
    assert isinstance(mod._build_client(), AsyncOpenAI)


def test_build_client_without_openai_names_the_install_command(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "openai", None)
    with pytest.raises(SystemExit, match=r"the 'openai' package is required.*pip install"):
        mod._build_client()


# --- one fixture in isolation ---


async def test_process_reports_up_to_date_without_synthesising(tmp_path: Path) -> None:
    """The cache check lives in AudioSynthesizer.process too, so a direct caller cannot skip it."""
    audio = tmp_path / "t.wav"
    audio.write_bytes(b"existing")
    (tmp_path / "t.wav.hash").write_text(mod.AudioFixture(transcript="Hello", audio_path=audio).expected_hash + "\n")
    spy = SynthSpy()
    fixture = mod.AudioFixture(transcript="Hello", audio_path=audio)

    action = await _synthesizer(spy).process(fixture, force=False)

    assert action == "up-to-date"
    assert spy.count == 0
    assert audio.read_bytes() == b"existing"


async def test_the_synthesizer_closes_its_client_on_the_way_out() -> None:
    """The client lifecycle is the synthesizer's, so a raising turn cannot leak the socket."""
    spy = SynthSpy()

    with pytest.raises(RuntimeError, match="boom"):
        async with mod.AudioSynthesizer(spy.client_factory(), voice="v", model="m", synth=spy):
            raise RuntimeError("boom")

    assert spy.client_closed


def test_audio_fixture_derives_its_sidecar_path_and_digest(tmp_path: Path) -> None:
    """The sidecar sits beside the WAV with the suffix appended, not replaced."""
    fixture = mod.AudioFixture(transcript="Hello", audio_path=tmp_path / "clip.wav")

    assert fixture.hash_path == tmp_path / "clip.wav.hash"
    assert fixture.expected_hash == hashlib.sha256(b"Hello").hexdigest()
    assert not fixture.is_up_to_date(force=False)


# --- CLI-level failure paths ---


async def test_no_paths_and_no_config_is_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], synth_spy: SynthSpy
) -> None:
    monkeypatch.chdir(tmp_path)

    rc = await _run_with(synth_spy, _args([]))

    assert rc == 1
    assert "no paths given" in capsys.readouterr().err


async def test_no_yaml_files_found_is_not_a_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], synth_spy: SynthSpy
) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()

    rc = await _run_with(synth_spy, _args([str(empty)]))

    assert rc == 0
    assert "No YAML files found." in capsys.readouterr().out


async def test_a_failed_turn_is_reported_and_sets_exit_code_two(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """One bad turn must not abort the others, but must still fail the run."""
    monkeypatch.setattr(mod, "_INTER_TURN_DELAY_S", 0.0)
    monkeypatch.setattr(mod, "_RETRY_BASE_DELAY_S", 0.0)
    _make_yaml(tmp_path / "a.yaml", audio_name="a.wav", user="alpha")
    _make_yaml(tmp_path / "b.yaml", audio_name="b.wav", user="bravo")
    spy = SynthSpy(fail_with=RuntimeError("HTTP 400 Bad Request"), fail_times=1)

    rc = await mod._run(_args([str(tmp_path)]), synth=spy, client_factory=spy.client_factory)

    captured = capsys.readouterr()
    assert rc == 2
    assert "FAIL" in captured.err
    assert "1 failed." in captured.out
    # The second turn still ran and produced its WAV.
    assert (tmp_path / "b.wav").exists()
    assert spy.client_closed


def test_main_runs_the_pipeline_and_returns_its_exit_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["synthesize_audio"])

    assert mod.main() == 1
    assert "no paths given" in capsys.readouterr().err


def test_iter_yaml_files_ignores_non_yaml_paths(tmp_path: Path) -> None:
    """An explicitly-passed .txt or .md is skipped rather than treated as a transcript."""
    (tmp_path / "notes.txt").write_text("not yaml")
    yaml_file = tmp_path / "t.yaml"
    yaml_file.write_text("id: t\n")

    found = mod._iter_yaml_files([tmp_path / "notes.txt", yaml_file])

    assert found == [yaml_file]


def test_absolute_audio_paths_are_left_alone(tmp_path: Path) -> None:
    """An absolute audio: path must not be re-rooted at the YAML's directory."""
    absolute = tmp_path / "elsewhere" / "clip.wav"
    yaml_path = tmp_path / "sub" / "t.yaml"
    yaml_path.parent.mkdir(parents=True)
    yaml_path.write_text(f"id: t\nturns:\n  - user: hi\n    audio: {absolute}\n")

    assert mod._load_turns(yaml_path) == [mod.AudioFixture(transcript="hi", audio_path=absolute)]


async def test_duplicate_audio_targets_are_synthesised_once(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], synth_spy: SynthSpy
) -> None:
    """Two transcripts pointing the same text at the same WAV: the second sees a fresh hash."""
    _make_yaml(tmp_path / "a.yaml", audio_name="shared.wav", user="same text")
    _make_yaml(tmp_path / "b.yaml", audio_name="shared.wav", user="same text")

    rc = await _run_with(synth_spy, _args([str(tmp_path)]))

    assert rc == 0
    assert synth_spy.count == 1
    out = capsys.readouterr().out
    assert "synthesised" in out
    assert "up-to-date" in out
    assert "Synthesized 1 new WAVs" in out
