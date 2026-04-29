import os
import pytest
from pathlib import Path
from pytest_llm_eval.config import LLMEvalConfig, load_config_from_toml


def test_default_config():
    cfg = LLMEvalConfig()
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
        "[tool.llm_eval]\n"
        'model = "anthropic:claude-3-5-sonnet-latest"\n'
        "threshold = 0.9\n"
        "runs = 3\n"
        "live = true\n"
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
    assert cfg == LLMEvalConfig()  # all defaults


def test_load_from_toml_nonexistent_file(tmp_path: Path):
    cfg = load_config_from_toml(tmp_path / "missing.toml")
    assert cfg == LLMEvalConfig()


def test_yaml_dirs_list(tmp_path: Path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[tool.llm_eval]\nyaml_dirs = ["tests/a", "tests/b"]\n')
    cfg = load_config_from_toml(pyproject)
    assert cfg.yaml_dirs == ["tests/a", "tests/b"]
