"""Tests for group config parsing and aggregation."""

from __future__ import annotations

import pytest

from pytest_agent_eval.groups import (
    EvalOutcome,
    GroupConfig,
    build_group_markdown_lines,
    evaluate_groups,
    format_group_summary_lines,
    parse_groups,
)

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


# --- evaluate_groups ---


def _outcome(identity: str, outcome: str = "passed", tags: list[str] | None = None, markers: list[str] | None = None):
    return EvalOutcome(
        identity=identity,
        nodeid=f"tests/evals/{identity}.yaml::{identity}",
        outcome=outcome,
        tags=tags or [],
        markers=markers or [],
    )


def test_evaluate_groups_threshold_pass_and_fail():
    group = GroupConfig(name="booking", threshold=0.66, tags=["gate:booking"])
    outcomes = [
        _outcome("a", "passed", tags=["gate:booking"]),
        _outcome("b", "passed", tags=["gate:booking"]),
        _outcome("c", "failed", tags=["gate:booking"]),
        _outcome("unrelated", "failed"),
    ]
    (result,) = evaluate_groups([group], outcomes)
    assert result.total == 3
    assert result.passed_count == 2
    assert result.pass_rate == pytest.approx(2 / 3)
    assert result.passed is True
    assert result.failing == ["c"]

    strict = GroupConfig(name="booking", threshold=0.9, tags=["gate:booking"])
    (result,) = evaluate_groups([strict], outcomes)
    assert result.passed is False


def test_evaluate_groups_matches_on_markers_or_tags():
    group = GroupConfig(name="g", tags=["gate:x"], pytest_markers=["smoke"])
    outcomes = [
        _outcome("by_tag", "passed", tags=["gate:x"]),
        _outcome("by_marker", "passed", markers=["smoke"]),
        _outcome("neither", "passed"),
    ]
    (result,) = evaluate_groups([group], outcomes)
    assert result.total == 2


def test_evaluate_groups_skips_excluded_from_denominator():
    group = GroupConfig(name="g", threshold=1.0, tags=["t"])
    outcomes = [
        _outcome("ran", "passed", tags=["t"]),
        _outcome("skipped_one", "skipped", tags=["t"]),
    ]
    (result,) = evaluate_groups([group], outcomes)
    assert result.total == 1
    assert result.skipped_count == 1
    assert result.passed is True


def test_evaluate_groups_all_skipped_is_not_a_pass():
    group = GroupConfig(name="g", tags=["t"])
    (result,) = evaluate_groups([group], [_outcome("s", "skipped", tags=["t"])])
    assert result.skipped is True
    assert result.passed is False


def test_evaluate_groups_zero_match():
    group = GroupConfig(name="g", tags=["t"])
    (result,) = evaluate_groups([group], [_outcome("x", "passed")])
    assert result.matched is False
    assert result.passed is False


def test_must_pass_failure_fails_group_even_above_threshold():
    group = GroupConfig(name="g", threshold=0.5, tags=["t"], must_pass=["critical"])
    outcomes = [
        _outcome("a", "passed", tags=["t"]),
        _outcome("b", "passed", tags=["t"]),
        _outcome("critical", "failed", tags=["t"]),
    ]
    (result,) = evaluate_groups([group], outcomes)
    assert result.pass_rate >= 0.5
    assert result.must_pass_failed == ["critical"]
    assert result.passed is False


def test_must_pass_matches_parametrized_identities():
    group = GroupConfig(name="g", tags=["t"], must_pass=["test_thing"])
    outcomes = [
        _outcome("test_thing[a]", "passed", tags=["t"]),
        _outcome("test_thing[b]", "failed", tags=["t"]),
        _outcome("test_thing_else", "passed", tags=["t"]),
    ]
    (result,) = evaluate_groups([group], outcomes)
    assert result.must_pass_failed == ["test_thing"]


def test_must_pass_entry_that_never_ran_is_missing_not_failed():
    group = GroupConfig(name="g", threshold=0.0, tags=["t"], must_pass=["absent"])
    (result,) = evaluate_groups([group], [_outcome("a", "passed", tags=["t"])])
    assert result.must_pass_missing == ["absent"]
    assert result.must_pass_failed == []
    assert result.passed is True


def test_must_pass_is_assertion_not_selector():
    """A must_pass entry that fails outside the tag selection still fails the group."""
    group = GroupConfig(name="g", tags=["t"], must_pass=["outside"])
    outcomes = [
        _outcome("a", "passed", tags=["t"]),
        _outcome("outside", "failed"),
    ]
    (result,) = evaluate_groups([group], outcomes)
    assert result.must_pass_failed == ["outside"]
    assert result.passed is False


# --- formatting ---


def test_format_group_summary_lines_shows_failures_even_when_group_passes():
    group = GroupConfig(name="g", threshold=0.5, tags=["t"])
    outcomes = [
        _outcome("a", "passed", tags=["t"]),
        _outcome("b", "failed", tags=["t"]),
    ]
    lines = format_group_summary_lines(evaluate_groups([group], outcomes))
    assert any("PASSED" in line for line in lines)
    assert any("failures: b" in line for line in lines)


def test_format_group_summary_lines_warns_on_zero_match():
    group = GroupConfig(name="ghost", tags=["t"])
    lines = format_group_summary_lines(evaluate_groups([group], []))
    assert lines == ["WARNING: group 'ghost' matched no tests"]


def test_format_group_summary_lines_skipped_row():
    group = GroupConfig(name="g", tags=["t"])
    lines = format_group_summary_lines(evaluate_groups([group], [_outcome("s", "skipped", tags=["t"])]))
    assert "SKIPPED" in lines[0]


def test_build_group_markdown_lines_contains_table_and_notes():
    group = GroupConfig(name="g", threshold=0.5, tags=["t"], must_pass=["absent"])
    outcomes = [
        _outcome("a", "passed", tags=["t"]),
        _outcome("b", "failed", tags=["t"]),
    ]
    lines = build_group_markdown_lines(evaluate_groups([group], outcomes))
    assert lines[0] == "## Groups"
    assert any("| g | 1 | 2 |" in line for line in lines)
    assert any("failures: b" in line for line in lines)
    assert any("did not run: absent" in line for line in lines)


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


def test_yaml_item_marker_carries_transcript_tags(pytester: pytest.Pytester):
    pytester.makeini("[pytest]\nasyncio_mode = auto\n")
    pytester.makefile(
        ".yaml",
        **{"tests/evals/tagged": ("id: tagged_test\ntags: [gate:booking]\nturns:\n  - user: hi\n")},
    )
    pytester.makeconftest(
        """
        import pytest

        @pytest.fixture
        def llm_eval_agent():
            async def agent(history):
                return "ok", []
            return agent


        def pytest_collection_modifyitems(items):
            for item in items:
                marker = item.get_closest_marker("agent_eval")
                if marker is not None:
                    print(f"TAGS={marker.kwargs.get('tags')}")
        """
    )
    result = pytester.runpytest("--agent-eval-live", "-s", "--collect-only")
    result.stdout.fnmatch_lines(["TAGS=*gate:booking*"])


def test_group_pytest_markers_are_auto_registered(pytester: pytest.Pytester):
    pytester.makepyprojecttoml(
        """
        [tool.agent_eval.groups.smoke]
        pytest_markers = ["smoke"]
        """
    )
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.smoke
        def test_marked():
            pass
        """
    )
    result = pytester.runpytest("-W", "error::pytest.PytestUnknownMarkWarning")
    assert result.ret == 0


_GROUPS_CONFTEST = """
import pytest

@pytest.fixture
def llm_eval_agent():
    async def agent(history):
        reply = "confirmed" if "good" in history[-1]["content"] else "nope"
        return reply, []
    return agent
"""


def _make_grouped_project(pytester: pytest.Pytester, threshold: float = 0.5, extra_toml: str = "") -> None:
    pytester.makepyprojecttoml(
        f"""
        [tool.agent_eval]
        yaml_dirs = ["tests/evals"]

        [tool.agent_eval.groups.booking]
        threshold = {threshold}
        tags = ["gate:booking"]
        {extra_toml}
        """
    )
    pytester.makeini("[pytest]\nasyncio_mode = auto\n")
    pytester.makeconftest(_GROUPS_CONFTEST)
    pytester.makefile(
        ".yaml",
        **{
            "tests/evals/good": (
                "id: good_case\nthreshold: 1.0\ntags: [gate:booking]\nturns:\n"
                "  - user: good\n    expect:\n      reply_contains_any: [confirmed]\n"
            ),
            "tests/evals/bad": (
                "id: bad_case\nthreshold: 1.0\ntags: [gate:booking]\nturns:\n"
                "  - user: bad\n    expect:\n      reply_contains_any: [confirmed]\n"
            ),
        },
    )


def test_terminal_group_summary_shows_rates_and_failures(pytester: pytest.Pytester):
    _make_grouped_project(pytester, threshold=0.5)
    result = pytester.runpytest("--agent-eval-live")
    result.stdout.fnmatch_lines(
        [
            "*group summary*",
            "*booking: 1/2 passed (50%) >= 50% required -- PASSED*",
            "*failures: bad_case*",
        ]
    )


def test_markdown_report_includes_groups_section(pytester: pytest.Pytester, tmp_path):
    _make_grouped_project(pytester, threshold=0.5)
    report_path = tmp_path / "report.md"
    pytester.runpytest("--agent-eval-live", f"--agent-eval-report={report_path}")
    content = report_path.read_text()
    assert "## Groups" in content
    assert "| booking | 1 | 2 |" in content
    assert content.index("## Groups") < content.index("## Details")


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
