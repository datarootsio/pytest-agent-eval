"""YAML transcript discovery and pytest collection."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Generator

import pytest
import yaml

from pytest_agent_eval.config import load_config
from pytest_agent_eval.models import Expect, JudgeConfig, ToolCallArgsConfig, Transcript, Turn
from pytest_agent_eval.runner import run_transcript


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
        KeyError: If required fields (id, turns[].user) are missing.
    """
    with open(path) as f:
        data: dict[str, Any] = yaml.safe_load(f)

    yaml_dir = path.parent
    return Transcript(
        id=data["id"],
        turns=[_parse_turn(t, yaml_dir) for t in data.get("turns", [])],
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
        transcript = load_transcript(self.path)
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
                "        return agent\n"
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
