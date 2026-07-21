"""Configuration loading for pytest-agent-eval."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from pytest_agent_eval.groups import GroupConfig, parse_groups


@dataclass
class AgentEvalConfig:
    """Runtime configuration for pytest-agent-eval.

    Args:
        model: pydantic-ai model string used by JudgeEvaluator (e.g. "openai:gpt-4o").
        threshold: Default fraction of runs that must pass (0.0-1.0).
        runs: Default number of times to run each test/transcript.
        retries: Number of retry attempts for the LLM judge on failure.
        timeout: Judge call timeout in seconds.
        yaml_dirs: Directories to search for YAML transcript files.
        live: Whether to actually run LLM tests (False = skip all agent_eval tests).
        report_path: Path to write markdown report, or None to skip.
        groups: Quality-gate groups parsed from [tool.agent_eval.groups].
    """

    model: str = "openai:gpt-4o"
    judge_model: str | None = None
    threshold: float = 0.8
    runs: int = 1
    retries: int = 2
    timeout: int = 30
    yaml_dirs: list[str] = field(default_factory=lambda: ["tests/evals"])
    live: bool = False
    report_path: str | None = None
    groups: list[GroupConfig] = field(default_factory=list)


def load_config_from_toml(path: Path) -> AgentEvalConfig:
    """Load [tool.agent_eval] from a pyproject.toml file.

    Args:
        path: Path to the pyproject.toml file.

    Returns:
        AgentEvalConfig with values from the file, defaults for missing keys.
    """
    cfg = AgentEvalConfig()
    if not path.exists():
        return cfg
    with open(path, "rb") as f:
        data = tomllib.load(f)
    section: dict[str, Any] = dict(data.get("tool", {}).get("agent_eval", {}))
    raw_groups = section.pop("groups", None)
    if raw_groups is not None:
        cfg.groups = parse_groups(raw_groups)
    for key, value in section.items():
        if hasattr(cfg, key):
            setattr(cfg, key, value)
    return cfg


def load_config(pytest_config: pytest.Config) -> AgentEvalConfig:
    """Load config from pyproject.toml, then apply CLI options and env vars.

    Priority (highest first): CLI flag > env var > pyproject.toml > defaults.

    Args:
        pytest_config: The pytest Config object.

    Returns:
        Resolved AgentEvalConfig.
    """
    rootdir = Path(str(pytest_config.rootdir))
    cfg = load_config_from_toml(rootdir / "pyproject.toml")

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
