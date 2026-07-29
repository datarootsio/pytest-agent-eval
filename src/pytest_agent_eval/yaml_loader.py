"""YAML transcript discovery, validation, and pytest collection."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
import yaml
from pydantic import ValidationError

from pytest_agent_eval._errors import SCHEMA_URL, TranscriptError, as_transcript_error
from pytest_agent_eval.config import load_config
from pytest_agent_eval.models import Transcript
from pytest_agent_eval.runner import JudgeSettings, run_transcript

if TYPE_CHECKING:
    from collections.abc import Generator

__all__ = [
    "SCHEMA_URL",
    "AgentEvalFile",
    "AgentEvalItem",
    "TranscriptError",
    "load_transcript",
    "pytest_collect_file",
    "validate_transcript_dict",
]


def validate_transcript_dict(data: object, source: str = "transcript") -> Transcript:
    """Parse a raw transcript document into a Transcript, raising on the first problem.

    Args:
        data: The parsed YAML document.
        source: Label used as the location prefix in error messages.

    Returns:
        The validated Transcript.

    Raises:
        TranscriptError: With a location-aware, suggestion-bearing message.
    """
    try:
        return Transcript.model_validate(data)
    except ValidationError as exc:
        raise as_transcript_error(exc, source, Transcript) from exc


def _resolve_audio_paths(transcript: Transcript, yaml_dir: Path) -> None:
    """Re-root each turn's relative audio path at the YAML file's directory.

    A post-parse step rather than a validator: a model has no idea which file it came
    from, and these models are mutable by design.
    """
    for turn in transcript.turns:
        if turn.audio is None:
            continue
        audio = Path(turn.audio)
        turn.audio = audio if audio.is_absolute() else yaml_dir / audio


def load_transcript(
    path: Path, *, default_threshold: float | None = None, default_runs: int | None = None
) -> Transcript:
    """Parse a YAML file into a Transcript.

    Args:
        path: Path to the YAML transcript file.
        default_threshold: Threshold when the document omits one (callers pass
            the [tool.agent_eval] value). None leaves the model default alone.
        default_runs: Run count when the document omits one. None leaves the
            model default alone.

    Returns:
        Parsed Transcript with all fields populated.

    Raises:
        TranscriptError: If the document fails validation.
    """
    transcript = validate_transcript_dict(yaml.safe_load(path.read_text()), path.name)
    # `model_fields_set` is pydantic's own record of which keys the document supplied, so
    # a config default fills in only where the author was silent. Presence-based, never
    # truthiness: `threshold: 0.0` is a real value that `or default_threshold` would eat.
    # Assignment re-validates, because _StrictModel sets validate_assignment=True.
    # plugin.py solves the same problem for the Python API, over marker.kwargs — a
    # different mechanism because a pytest marker is not a pydantic model. Keep the two
    # in step: both are presence checks, and neither may become a truthiness check.
    if default_threshold is not None and "threshold" not in transcript.model_fields_set:
        transcript.threshold = default_threshold
    if default_runs is not None and "runs" not in transcript.model_fields_set:
        transcript.runs = default_runs
    _resolve_audio_paths(transcript, path.parent)
    return transcript


def pytest_collect_file(parent: pytest.Collector, file_path: Path) -> pytest.Collector | None:
    """Collect YAML transcript files from configured yaml_dirs."""
    if file_path.suffix not in (".yaml", ".yml"):
        return None

    cfg = load_config(parent.config)
    yaml_dirs = [parent.config.rootpath / d for d in cfg.yaml_dirs]

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
        cfg = load_config(self.config)
        try:
            transcript = load_transcript(self.path, default_threshold=cfg.threshold, default_runs=cfg.runs)
        except yaml.YAMLError as exc:
            mark = getattr(exc, "problem_mark", None)
            where = f" at line {mark.line + 1}, column {mark.column + 1}" if mark else ""
            problem = getattr(exc, "problem", None) or exc
            raise self.CollectError(
                f"{self.path.name}: invalid YAML{where}: {problem}\nSchema reference: {SCHEMA_URL}"
            ) from exc
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
        # Only request the fixture when it actually resolves for this node. Adding an
        # undefined name to the closure makes setup() raise FixtureLookupError, whose
        # formatrepr() does `self.request._pyfuncitem.obj` — an attribute only
        # function-based items have — turning a forgotten fixture into a pytest
        # INTERNALERROR instead of the didactic skip in runtest().
        if fm.getfixturedefs("llm_eval_agent", self) and "llm_eval_agent" not in fixtureinfo.names_closure:
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
        result = asyncio.run(
            run_transcript(
                self.transcript,
                agent,
                JudgeSettings(
                    config_model=cfg.model,
                    judge_model=cfg.judge_model,
                    retries=cfg.retries,
                    timeout=cfg.timeout,
                ),
            )
        )
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
