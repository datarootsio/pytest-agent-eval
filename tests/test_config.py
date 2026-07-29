from pathlib import Path

import pytest

from pytest_agent_eval.config import AgentEvalConfig, load_config, load_config_from_toml
from tests.helpers.config_fakes import FakePytestConfig


def test_default_config() -> None:
    cfg = AgentEvalConfig()
    assert cfg.model == "openai:gpt-4o"
    assert cfg.threshold == 0.8
    assert cfg.runs == 1
    assert cfg.retries == 2
    assert cfg.timeout == 30
    assert cfg.yaml_dirs == ["tests/evals"]
    assert cfg.live is False
    assert cfg.report_path is None


def test_load_from_toml(tmp_path: Path) -> None:
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


def test_load_from_toml_missing_section(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[tool.other]\nfoo = 1\n")
    cfg = load_config_from_toml(pyproject)
    assert cfg == AgentEvalConfig()  # all defaults


def test_load_from_toml_nonexistent_file(tmp_path: Path) -> None:
    cfg = load_config_from_toml(tmp_path / "missing.toml")
    assert cfg == AgentEvalConfig()


def test_yaml_dirs_list(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[tool.agent_eval]\nyaml_dirs = ["tests/a", "tests/b"]\n')
    cfg = load_config_from_toml(pyproject)
    assert cfg.yaml_dirs == ["tests/a", "tests/b"]


def test_load_config_env_var_sets_live(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """EVAL_LIVE=1 env var enables live mode even when TOML says live=false."""
    monkeypatch.setenv("EVAL_LIVE", "1")
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[tool.agent_eval]\nlive = false\n")

    cfg = load_config(
        FakePytestConfig(
            rootpath=tmp_path,
            unknown_option_error=pytest.UsageError("No option named: --agent-eval-live"),
        )
    )
    assert cfg.live is True


def test_load_config_cli_flag_sets_live(tmp_path: Path) -> None:
    """--agent-eval-live CLI flag enables live mode."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[tool.agent_eval]\nlive = false\n")

    cfg = load_config(FakePytestConfig(rootpath=tmp_path, options={"--agent-eval-live": True}))
    assert cfg.live is True


def test_unknown_agent_eval_keys_are_ignored(tmp_path: Path) -> None:
    """Deliberate, and documented as the contrast to strict [tool.agent_eval.groups]."""
    from pytest_agent_eval.config import load_config_from_toml

    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[tool.agent_eval]\nmodel = "openai:gpt-4o-mini"\nnot_a_real_option = 42\n')

    cfg = load_config_from_toml(pyproject)

    assert cfg.model == "openai:gpt-4o-mini"
    assert not hasattr(cfg, "not_a_real_option")


def test_invalid_threshold_is_rejected_at_load_time(tmp_path: Path) -> None:
    """Previously a blind setattr loop accepted any value and failed much later.

    A string threshold used to reach the runner and blow up in a score comparison, far
    from the line that caused it.
    """
    from pytest_agent_eval.config import load_config_from_toml

    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[tool.agent_eval]\nthreshold = "high"\n')

    with pytest.raises(ValueError, match="threshold"):
        load_config_from_toml(pyproject)


@pytest.mark.parametrize(
    "body",
    [
        "threshold = 1.5",
        "threshold = -0.1",
        "runs = 0",
        "timeout = 0",
        "retries = -1",
        'yaml_dirs = "not-a-list"',
    ],
    ids=["threshold_high", "threshold_negative", "runs_zero", "timeout_zero", "retries_negative", "yaml_dirs_scalar"],
)
def test_out_of_range_config_values_are_rejected(tmp_path: Path, body: str) -> None:
    from pytest_agent_eval.config import load_config_from_toml

    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(f"[tool.agent_eval]\n{body}\n")

    with pytest.raises(ValueError):
        load_config_from_toml(pyproject)


def test_group_config_errors_survive_the_config_model(tmp_path: Path) -> None:
    """parse_groups' strict messages must not be replaced by pydantic's generic ones."""
    from pytest_agent_eval.config import load_config_from_toml

    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[tool.agent_eval.groups.booking]\nmust_pas = []\n")

    with pytest.raises(ValueError, match="unknown key"):
        load_config_from_toml(pyproject)
