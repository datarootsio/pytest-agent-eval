"""YAML transcript discovery and pytest collection."""
from __future__ import annotations
import asyncio
from pathlib import Path
from typing import Generator, Any
import yaml
import pytest
from pytest_llm_eval.config import load_config
from pytest_llm_eval.models import (
    Transcript, Turn, Expect, JudgeConfig
)
from pytest_llm_eval.runner import run_transcript


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

    turns: list[Turn] = []
    for raw_turn in data.get("turns", []):
        raw_expect = raw_turn.get("expect", {})
        judge_cfg: JudgeConfig | None = None
        if "judge" in raw_expect:
            j = raw_expect["judge"]
            judge_cfg = JudgeConfig(rubric=j["rubric"], model=j.get("model"))

        expect = Expect(
            judge=judge_cfg,
            tool_calls_include=raw_expect.get("tool_calls_include", []),
            tool_calls_exclude=raw_expect.get("tool_calls_exclude", []),
            reply_contains_any=raw_expect.get("reply_contains_any", []),
            reply_contains_all=raw_expect.get("reply_contains_all", []),
        )
        turns.append(Turn(user=raw_turn["user"], expect=expect))

    return Transcript(
        id=data["id"],
        turns=turns,
        threshold=data.get("threshold", 0.8),
        runs=data.get("runs", 1),
        tags=data.get("tags", []),
    )


def pytest_collect_file(
    parent: pytest.Collector, file_path: Path
) -> pytest.Collector | None:
    """Collect YAML transcript files from configured yaml_dirs."""
    if file_path.suffix not in (".yaml", ".yml"):
        return None

    cfg = load_config(parent.config)
    rootdir = Path(str(parent.config.rootdir))
    yaml_dirs = [rootdir / d for d in cfg.yaml_dirs]

    for yaml_dir in yaml_dirs:
        try:
            file_path.relative_to(yaml_dir.resolve())
            return LLMEvalFile.from_parent(parent, path=file_path)
        except ValueError:
            continue
    return None


class LLMEvalFile(pytest.File):
    """Pytest collector for a single YAML transcript file."""

    def collect(self) -> Generator[pytest.Item, None, None]:
        transcript = load_transcript(self.path)
        yield LLMEvalItem.from_parent(self, name=transcript.id, transcript=transcript)


class LLMEvalItem(pytest.Item):
    """Pytest item representing one YAML transcript test."""

    # Tell pytest not to inspect a function for argnames — we wire fixtures manually.
    nofuncargs = True

    def __init__(self, *, transcript: Transcript, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.transcript = transcript
        self.add_marker(
            pytest.mark.llm_eval(
                threshold=transcript.threshold,
                runs=transcript.runs,
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
        result = asyncio.run(run_transcript(self.transcript, agent, cfg.model))
        self._eval_result = result
        result.assert_threshold()

    def repr_failure(self, excinfo: Any) -> str:
        if isinstance(excinfo.value, AssertionError):
            return str(excinfo.value)
        return super().repr_failure(excinfo)

    def reportinfo(self) -> tuple[Any, int | None, str]:
        return self.fspath, None, f"llm_eval: {self.transcript.id}"
