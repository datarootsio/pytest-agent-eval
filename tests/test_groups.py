"""Tests for group config parsing and aggregation."""

from __future__ import annotations

import pytest

from pytest_agent_eval.groups import GroupConfig, parse_groups

# --- parse_groups ---


def test_parse_groups_full_config():
    groups = parse_groups(
        {
            "booking": {
                "threshold": 0.9,
                "tags": ["gate:booking"],
                "pytest_markers": ["booking"],
                "must_pass": ["booking_confirmation"],
            },
            "smoke": {"tags": ["smoke"]},
        }
    )
    assert groups[0] == GroupConfig(
        name="booking",
        threshold=0.9,
        tags=["gate:booking"],
        pytest_markers=["booking"],
        must_pass=["booking_confirmation"],
    )
    assert groups[1].threshold == 1.0
    assert groups[1].tags == ["smoke"]


def test_parse_groups_rejects_unknown_key():
    with pytest.raises(ValueError, match="unknown key.*must_pas"):
        parse_groups({"g": {"must_pas": ["typo"]}})


def test_parse_groups_rejects_threshold_out_of_range():
    with pytest.raises(ValueError, match="threshold"):
        parse_groups({"g": {"threshold": 1.5}})


def test_parse_groups_rejects_non_numeric_threshold():
    with pytest.raises(ValueError, match="threshold"):
        parse_groups({"g": {"threshold": "0.9"}})


def test_parse_groups_rejects_non_list_tags():
    with pytest.raises(ValueError, match="tags"):
        parse_groups({"g": {"tags": "gate:booking"}})


def test_parse_groups_rejects_non_table_group():
    with pytest.raises(ValueError, match="must be a table"):
        parse_groups({"g": 0.9})


# --- config wiring ---


def test_load_config_parses_groups_section(tmp_path):
    from pytest_agent_eval.config import load_config_from_toml

    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        "[tool.agent_eval]\n"
        'model = "openai:gpt-4o"\n'
        "[tool.agent_eval.groups.booking]\n"
        "threshold = 0.9\n"
        'tags = ["gate:booking"]\n'
    )
    cfg = load_config_from_toml(pyproject)
    assert cfg.model == "openai:gpt-4o"
    assert len(cfg.groups) == 1
    assert cfg.groups[0].name == "booking"
    assert cfg.groups[0].threshold == 0.9


def test_invalid_group_config_becomes_usage_error(pytester: pytest.Pytester):
    pytester.makepyprojecttoml(
        """
        [tool.agent_eval.groups.booking]
        must_pas = ["typo"]
        """
    )
    pytester.makepyfile("def test_ok(): pass")
    result = pytester.runpytest()
    assert result.ret == pytest.ExitCode.USAGE_ERROR
    result.stderr.fnmatch_lines(["*must_pas*"])
