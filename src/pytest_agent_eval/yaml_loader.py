"""YAML transcript discovery, validation, and pytest collection."""

from __future__ import annotations

import asyncio
import difflib
from pathlib import Path
from typing import Any, Generator

import pytest
import yaml

from pytest_agent_eval.config import load_config
from pytest_agent_eval.models import Expect, JudgeConfig, ToolCallArgsConfig, Transcript, Turn
from pytest_agent_eval.runner import run_transcript

SCHEMA_URL = "https://datarootsio.github.io/pytest-agent-eval/latest/schema/transcript.json"

TOP_LEVEL_FIELDS = frozenset({"id", "threshold", "runs", "tags", "turns"})
TURN_FIELDS = frozenset({"user", "audio", "expect"})
EXPECT_FIELDS = frozenset(
    {
        "judge",
        "tool_calls_include",
        "tool_calls_exclude",
        "tool_calls_ordered",
        "tool_calls_args",
        "reply_contains_any",
        "reply_contains_all",
        "reply_matches_any",
        "reply_matches_all",
    }
)
JUDGE_FIELDS = frozenset({"rubric", "model"})
TOOL_CALLS_ARGS_FIELDS = frozenset({"tool", "args", "mode", "judge"})

_LIST_OF_STR_EXPECT_FIELDS = (
    "tool_calls_include",
    "tool_calls_exclude",
    "reply_contains_any",
    "reply_contains_all",
    "reply_matches_any",
    "reply_matches_all",
)


class TranscriptError(ValueError):
    """A YAML transcript failed validation, with a didactic location-aware message."""


def _fail(location: str, message: str) -> TranscriptError:
    return TranscriptError(f"{location}: {message}\nSchema reference: {SCHEMA_URL}")


def _check_keys(raw: dict[str, Any], valid: frozenset[str], location: str) -> None:
    for key in raw:
        if key not in valid:
            close = difflib.get_close_matches(str(key), sorted(valid), n=1)
            hint = f" Did you mean {close[0]!r}?" if close else ""
            raise _fail(location, f"unknown field {key!r}.{hint} Valid fields: {sorted(valid)}.")


def _check_list_of_str(value: Any, location: str) -> None:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise _fail(
            location,
            f"must be a list of strings, got {type(value).__name__} ({value!r}). "
            f"YAML lists look like:\n  {location.rsplit('.', 1)[-1]}:\n    - first item\n    - second item",
        )


def _check_judge(raw: Any, location: str) -> None:
    if not isinstance(raw, dict):
        raise _fail(location, f"must be a mapping with a 'rubric' key, got {type(raw).__name__} ({raw!r})")
    _check_keys(raw, JUDGE_FIELDS, location)
    if "rubric" not in raw:
        raise _fail(location, "missing required field 'rubric' (the natural-language criteria for the judge)")
    if not isinstance(raw["rubric"], str):
        raise _fail(f"{location}.rubric", f"must be a string, got {type(raw['rubric']).__name__}")
    if "model" in raw and not isinstance(raw["model"], str):
        raise _fail(f"{location}.model", f"must be a string like 'openai:gpt-4o', got {type(raw['model']).__name__}")


def _check_tool_calls_args(raw: Any, location: str) -> None:
    if not isinstance(raw, list):
        raise _fail(location, f"must be a list of tool-argument assertions, got {type(raw).__name__}")
    for i, entry in enumerate(raw):
        loc = f"{location}[{i}]"
        if not isinstance(entry, dict):
            raise _fail(loc, f"must be a mapping with a 'tool' key, got {type(entry).__name__} ({entry!r})")
        _check_keys(entry, TOOL_CALLS_ARGS_FIELDS, loc)
        if "tool" not in entry or not isinstance(entry["tool"], str):
            raise _fail(loc, "requires a 'tool' field naming the tool whose arguments to check")
        if "args" not in entry and "judge" not in entry:
            raise _fail(loc, "needs 'args' (deterministic check) or 'judge' (LLM-judged rubric); got neither")
        if "args" in entry and not isinstance(entry["args"], dict):
            raise _fail(f"{loc}.args", f"must be a mapping of expected arguments, got {type(entry['args']).__name__}")
        if "mode" in entry and entry["mode"] not in ("subset", "exact"):
            raise _fail(f"{loc}.mode", f"must be 'subset' or 'exact', got {entry['mode']!r}")
        if "judge" in entry:
            _check_judge(entry["judge"], f"{loc}.judge")


def _check_expect(raw: Any, location: str) -> None:
    if not isinstance(raw, dict):
        raise _fail(location, f"must be a mapping of expectations, got {type(raw).__name__} ({raw!r})")
    _check_keys(raw, EXPECT_FIELDS, location)
    for field in _LIST_OF_STR_EXPECT_FIELDS:
        if field in raw:
            _check_list_of_str(raw[field], f"{location}.{field}")
    if "tool_calls_ordered" in raw and not isinstance(raw["tool_calls_ordered"], bool):
        raise _fail(f"{location}.tool_calls_ordered", f"must be true or false, got {raw['tool_calls_ordered']!r}")
    if "judge" in raw:
        _check_judge(raw["judge"], f"{location}.judge")
    if "tool_calls_args" in raw:
        _check_tool_calls_args(raw["tool_calls_args"], f"{location}.tool_calls_args")


def validate_transcript_dict(data: Any, source: str = "transcript") -> None:
    """Validate a raw transcript mapping before dataclass construction.

    Args:
        data: The parsed YAML document.
        source: Label used as the location prefix in error messages.

    Raises:
        TranscriptError: With a location-aware, suggestion-bearing message on
            the first problem found.
    """
    if not isinstance(data, dict):
        raise _fail(source, f"must be a YAML mapping with 'id' and 'turns' keys, got {type(data).__name__}")
    _check_keys(data, TOP_LEVEL_FIELDS, source)

    if "id" not in data:
        raise _fail(source, "missing required field 'id' (a unique name; it becomes the pytest test name)")
    if not isinstance(data["id"], str):
        raise _fail(f"{source}.id", f"must be a string, got {type(data['id']).__name__}")

    if "threshold" in data:
        threshold = data["threshold"]
        if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not 0.0 <= threshold <= 1.0:
            raise _fail(f"{source}.threshold", f"must be a number between 0 and 1, got {threshold!r}")
    if "runs" in data:
        runs = data["runs"]
        if isinstance(runs, bool) or not isinstance(runs, int) or runs < 1:
            raise _fail(f"{source}.runs", f"must be an integer >= 1, got {runs!r}")
    if "tags" in data:
        _check_list_of_str(data["tags"], f"{source}.tags")

    turns = data.get("turns")
    if not turns:
        raise _fail(source, "must define at least one turn under 'turns' (an empty transcript would test nothing)")
    if not isinstance(turns, list):
        raise _fail(f"{source}.turns", f"must be a list of turns, got {type(turns).__name__}")
    for i, turn in enumerate(turns):
        loc = f"turns[{i}]"
        if not isinstance(turn, dict):
            raise _fail(loc, f"must be a mapping with a 'user' key, got {type(turn).__name__} ({turn!r})")
        _check_keys(turn, TURN_FIELDS, loc)
        if "user" not in turn:
            raise _fail(loc, "missing required field 'user' (the user message for this turn)")
        if not isinstance(turn["user"], str):
            raise _fail(f"{loc}.user", f"must be a string, got {type(turn['user']).__name__}")
        if "audio" in turn and not isinstance(turn["audio"], str):
            raise _fail(f"{loc}.audio", f"must be a WAV path string, got {type(turn['audio']).__name__}")
        if "expect" in turn:
            _check_expect(turn["expect"], f"{loc}.expect")


def _parse_tool_calls_args(raw: list[dict[str, Any]]) -> list[ToolCallArgsConfig]:
    return [
        ToolCallArgsConfig(
            tool=entry["tool"],
            args=entry.get("args"),
            mode=entry.get("mode", "subset"),
            judge=(
                JudgeConfig(rubric=entry["judge"]["rubric"], model=entry["judge"].get("model"))
                if "judge" in entry
                else None
            ),
        )
        for entry in raw
    ]


def _parse_turn(raw_turn: dict[str, Any], yaml_dir: Path) -> Turn:
    raw_expect = raw_turn.get("expect", {})
    judge_cfg: JudgeConfig | None = None
    if "judge" in raw_expect:
        j = raw_expect["judge"]
        judge_cfg = JudgeConfig(rubric=j["rubric"], model=j.get("model"))
    expect = Expect(
        judge=judge_cfg,
        tool_calls_include=raw_expect.get("tool_calls_include", []),
        tool_calls_exclude=raw_expect.get("tool_calls_exclude", []),
        tool_calls_ordered=raw_expect.get("tool_calls_ordered", False),
        tool_calls_args=_parse_tool_calls_args(raw_expect.get("tool_calls_args", [])),
        reply_contains_any=raw_expect.get("reply_contains_any", []),
        reply_contains_all=raw_expect.get("reply_contains_all", []),
        reply_matches_any=raw_expect.get("reply_matches_any", []),
        reply_matches_all=raw_expect.get("reply_matches_all", []),
    )
    audio_raw = raw_turn.get("audio")
    audio: Path | None = None
    if audio_raw is not None:
        audio_path = Path(audio_raw)
        audio = audio_path if audio_path.is_absolute() else (yaml_dir / audio_path)
    return Turn(user=raw_turn["user"], audio=audio, expect=expect)


def load_transcript(path: Path) -> Transcript:
    """Parse a YAML file into a Transcript.

    Args:
        path: Path to the YAML transcript file.

    Returns:
        Parsed Transcript with all fields populated.

    Raises:
        TranscriptError: If the document fails validation.
    """
    with open(path) as f:
        data: dict[str, Any] = yaml.safe_load(f)

    validate_transcript_dict(data, source=path.name)

    yaml_dir = path.parent
    return Transcript(
        id=data["id"],
        turns=[_parse_turn(t, yaml_dir) for t in data["turns"]],
        threshold=data.get("threshold", 0.8),
        runs=data.get("runs", 1),
        tags=data.get("tags", []),
    )


def pytest_collect_file(parent: pytest.Collector, file_path: Path) -> pytest.Collector | None:
    """Collect YAML transcript files from configured yaml_dirs."""
    if file_path.suffix not in (".yaml", ".yml"):
        return None

    cfg = load_config(parent.config)
    rootdir = Path(str(parent.config.rootdir))
    yaml_dirs = [rootdir / d for d in cfg.yaml_dirs]

    for yaml_dir in yaml_dirs:
        try:
            file_path.relative_to(yaml_dir.resolve())
            return AgentEvalFile.from_parent(parent, path=file_path)
        except ValueError:
            continue
    return None


class AgentEvalFile(pytest.File):
    """Pytest collector for a single YAML transcript file."""

    def collect(self) -> Generator[pytest.Item, None, None]:
        """Yield a single AgentEvalItem for this YAML transcript."""
        try:
            transcript = load_transcript(self.path)
        except TranscriptError as exc:
            raise self.CollectError(str(exc)) from exc
        yield AgentEvalItem.from_parent(self, name=transcript.id, transcript=transcript)


class AgentEvalItem(pytest.Item):
    """Pytest item representing one YAML transcript test."""

    # Tell pytest not to inspect a function for argnames — we wire fixtures manually.
    nofuncargs = True

    def __init__(self, *, transcript: Transcript, **kwargs: Any) -> None:
        """Wire transcript fixtures and the agent_eval marker onto the pytest item."""
        super().__init__(**kwargs)
        self.transcript = transcript
        self.add_marker(
            pytest.mark.agent_eval(
                threshold=transcript.threshold,
                runs=transcript.runs,
                tags=transcript.tags,
            )
        )
        self._eval_result: Any = None

        # Wire up pytest fixture machinery so llm_eval_agent is injected.
        fm = self.session._fixturemanager
        fixtureinfo = fm.getfixtureinfo(node=self, func=None, cls=None)
        # Append our required fixture to the closure so pytest resolves it.
        if "llm_eval_agent" not in fixtureinfo.names_closure:
            fixtureinfo.names_closure.append("llm_eval_agent")
        self._fixtureinfo = fixtureinfo
        self.fixturenames = fixtureinfo.names_closure
        self.funcargs: dict[str, Any] = {}
        from _pytest.fixtures import TopRequest

        self._request = TopRequest(self, _ispytest=True)

    def setup(self) -> None:
        """Resolve fixtures into funcargs before runtest is called."""
        self._request._fillfixtures()

    def runtest(self) -> None:
        """Execute the transcript against the configured agent and assert threshold."""
        agent = self.funcargs.get("llm_eval_agent")
        if agent is None:
            pytest.skip(
                "llm_eval_agent fixture not defined. "
                "Add it to your conftest.py:\n\n"
                "    @pytest.fixture\n"
                "    def llm_eval_agent():\n"
                "        async def agent(history): ...\n"
                "        return agent\n\n"
                "Docs: https://datarootsio.github.io/pytest-agent-eval/latest/yaml-api/#agent-fixture"
            )
        cfg = load_config(self.config)
        result = asyncio.run(run_transcript(self.transcript, agent, cfg.model, cfg.judge_model))
        self._eval_result = result
        result.assert_threshold()

    def repr_failure(self, excinfo: Any) -> str:
        """Render assertion errors plainly; defer other failures to pytest."""
        if isinstance(excinfo.value, AssertionError):
            return str(excinfo.value)
        return super().repr_failure(excinfo)

    def reportinfo(self) -> tuple[Any, int | None, str]:
        """Provide the location string pytest shows for this item."""
        # Line 0, not None: pytest rewrites a marker-skipped test's longrepr to its
        # reportinfo location and (since 9.1) asserts the line is not None.
        return self.fspath, 0, f"agent_eval: {self.transcript.id}"
