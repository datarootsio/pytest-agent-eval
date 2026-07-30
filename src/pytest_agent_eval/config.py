"""Configuration loading for pytest-agent-eval."""

from __future__ import annotations

import os
import tomllib
from typing import TYPE_CHECKING

import pytest
from pydantic import BaseModel, ConfigDict, Field, field_validator

from pytest_agent_eval.groups import GroupConfig, parse_groups
from pytest_agent_eval.models import DEFAULT_RUNS, DEFAULT_THRESHOLD

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_agent_eval.models import JsonMapping


class AgentEvalConfig(BaseModel):
    """Runtime configuration for pytest-agent-eval.

    Unknown keys under ``[tool.agent_eval]`` are ignored, which is deliberate and
    contrasts with ``[tool.agent_eval.groups]``: a typo there would silently disable a
    CI gate, whereas a typo here leaves a documented default in place.

    Attributes:
        model: pydantic-ai model string used by JudgeEvaluator (e.g. "openai:gpt-4o").
        judge_model: Dedicated judge model; takes priority over ``model``.
        threshold: Default fraction of runs that must pass (0.0-1.0).
        runs: Default number of times to run each test/transcript.
        retries: Number of retry attempts for the LLM judge on failure.
        timeout: Judge call timeout in seconds.
        yaml_dirs: Directories to search for YAML transcript files.
        live: Whether to actually run LLM tests (False = skip all agent_eval tests).
        report_path: Path to write markdown report, or None to skip.
        groups: Quality-gate groups parsed from [tool.agent_eval.groups].
    """

    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    model: str = "openai:gpt-4o"
    judge_model: str | None = None
    threshold: float = Field(default=DEFAULT_THRESHOLD, ge=0.0, le=1.0)
    runs: int = Field(default=DEFAULT_RUNS, ge=1)
    retries: int = Field(default=2, ge=0)
    timeout: int = Field(default=30, gt=0)
    yaml_dirs: list[str] = Field(default_factory=lambda: ["tests/evals"])
    live: bool = False
    report_path: str | None = None
    groups: list[GroupConfig] = Field(default_factory=list)

    @field_validator("groups", mode="before")
    @classmethod
    def _parse_group_tables(cls, value: object) -> object:
        """Turn the raw [tool.agent_eval.groups] tables into GroupConfigs.

        Kept as a before-validator so parse_groups' strict, didactic messages survive
        rather than being replaced by pydantic's generic ones.
        """
        return parse_groups(value) if isinstance(value, dict) else value


def load_config_from_toml(path: Path) -> AgentEvalConfig:
    """Load [tool.agent_eval] from a pyproject.toml file.

    Args:
        path: Path to the pyproject.toml file.

    Returns:
        AgentEvalConfig with values from the file, defaults for missing keys.
    """
    if not path.exists():
        return AgentEvalConfig()
    data = tomllib.loads(path.read_text())
    section: JsonMapping = dict(data.get("tool", {}).get("agent_eval", {}))
    return AgentEvalConfig.model_validate(section)


def load_config(pytest_config: pytest.Config) -> AgentEvalConfig:
    """Load config from pyproject.toml, then apply CLI options and env vars.

    Priority (highest first): CLI flag > env var > pyproject.toml > defaults.

    Args:
        pytest_config: The pytest Config object.

    Returns:
        Resolved AgentEvalConfig.
    """
    cfg = load_config_from_toml(pytest_config.rootpath / "pyproject.toml")

    # Env var override
    if os.environ.get("EVAL_LIVE", "").lower() in ("1", "true", "yes"):
        cfg.live = True

    # CLI flag overrides
    try:
        if pytest_config.getoption("--agent-eval-live"):
            cfg.live = True
    except (ValueError, AttributeError, pytest.UsageError):
        pass

    try:
        report = pytest_config.getoption("--agent-eval-report")
        if report:
            cfg.report_path = report
    except (ValueError, AttributeError, pytest.UsageError):
        pass

    return cfg
