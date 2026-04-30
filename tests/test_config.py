from pathlib import Path
from unittest.mock import MagicMock

import pytest

from pytest_agent_eval.config import AgentEvalConfig, load_config, load_config_from_toml


def test_default_config():
    cfg = AgentEvalConfig()
    assert cfg.model == "openai:gpt-4o"
    assert cfg.threshold == 0.8
    assert cfg.runs == 1
    assert cfg.retries == 2
    assert cfg.timeout == 30
    assert cfg.yaml_dirs == ["tests/evals"]
    assert cfg.live is False
    assert cfg.report_path is None


def test_load_from_toml(tmp_path: Path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[tool.agent_eval]\nmodel = "anthropic:claude-3-5-sonnet-latest"\nthreshold = 0.9\nruns = 3\nlive = true\n'
    )
    cfg = load_config_from_toml(pyproject)
    assert cfg.model == "anthropic:claude-3-5-sonnet-latest"
    assert cfg.threshold == 0.9
    assert cfg.runs == 3
    assert cfg.live is True
    assert cfg.retries == 2  # default preserved


def test_load_from_toml_missing_section(tmp_path: Path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[tool.other]\nfoo = 1\n")
    cfg = load_config_from_toml(pyproject)
    assert cfg == AgentEvalConfig()  # all defaults


def test_load_from_toml_nonexistent_file(tmp_path: Path):
    cfg = load_config_from_toml(tmp_path / "missing.toml")
    assert cfg == AgentEvalConfig()


def test_yaml_dirs_list(tmp_path: Path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[tool.agent_eval]\nyaml_dirs = ["tests/a", "tests/b"]\n')
    cfg = load_config_from_toml(pyproject)
    assert cfg.yaml_dirs == ["tests/a", "tests/b"]


def test_load_config_env_var_sets_live(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """EVAL_LIVE=1 env var enables live mode even when TOML says live=false."""
    monkeypatch.setenv("EVAL_LIVE", "1")
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[tool.agent_eval]\nlive = false\n")

    mock_config = MagicMock()
    mock_config.rootdir = tmp_path
    mock_config.getoption.side_effect = pytest.UsageError("No option named: --agent-eval-live")

    cfg = load_config(mock_config)
    assert cfg.live is True


def test_load_config_cli_flag_sets_live(tmp_path: Path):
    """--agent-eval-live CLI flag enables live mode."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[tool.agent_eval]\nlive = false\n")

    mock_config = MagicMock()
    mock_config.rootdir = tmp_path
    mock_config.getoption.side_effect = lambda name, **kw: True if name == "--agent-eval-live" else None

    cfg = load_config(mock_config)
    assert cfg.live is True
