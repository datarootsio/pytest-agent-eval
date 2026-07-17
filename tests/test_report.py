import types
from pathlib import Path
from typing import Any

import pytest

from pytest_agent_eval.models import EvalResult, RunResult, TranscriptResult, TurnResult
from pytest_agent_eval.report import (
    AgentEvalReportPlugin,
    _deserialize_result,
    _serialize_result,
    build_markdown_report,
)


def _make_full_result() -> TranscriptResult:
    return TranscriptResult(
        passed=True,
        score=0.75,
        threshold=0.5,
        runs=[
            RunResult(
                run_index=0,
                passed=True,
                turn_results=[
                    TurnResult(
                        turn_index=0,
                        passed=True,
                        eval_results=[EvalResult(passed=True, reasoning="looks good")],
                    )
                ],
            ),
            RunResult(
                run_index=1,
                passed=False,
                turn_results=[
                    TurnResult(
                        turn_index=0,
                        passed=False,
                        eval_results=[EvalResult(passed=False, reasoning="missing keyword")],
                    )
                ],
            ),
        ],
    )


def test_serialize_result_produces_dict():
    result = _make_full_result()
    data = _serialize_result(result)
    assert isinstance(data, dict)
    assert data["passed"] is True
    assert data["score"] == 0.75
    assert len(data["runs"]) == 2


def test_deserialize_result_roundtrip():
    original = _make_full_result()
    restored = _deserialize_result(_serialize_result(original))
    assert restored == original
    assert restored.runs[0].turn_results[0].eval_results[0].reasoning == "looks good"
    assert restored.runs[1].passed is False


def _make_result(passed: bool, score: float, threshold: float, name: str = "test") -> tuple[str, TranscriptResult]:
    run = RunResult(
        run_index=0,
        passed=passed,
        turn_results=[
            TurnResult(
                turn_index=0,
                passed=passed,
                eval_results=[EvalResult(passed=passed, reasoning="test reasoning")],
            )
        ],
    )
    return name, TranscriptResult(passed=passed, score=score, threshold=threshold, runs=[run])


def test_build_markdown_report_contains_summary_table():
    results = [
        _make_result(True, 1.0, 0.8, "booking_ok"),
        _make_result(False, 0.4, 0.8, "cancel_fail"),
    ]
    report = build_markdown_report(results)
    assert "# LLM Eval Report" in report
    assert "booking_ok" in report
    assert "cancel_fail" in report
    assert "PASS" in report
    assert "FAIL" in report


def test_build_markdown_report_shows_score():
    results = [_make_result(True, 0.75, 0.5, "test_score")]
    report = build_markdown_report(results)
    assert "0.75" in report
    assert "0.50" in report


def test_report_written_to_file_with_flag(pytester: pytest.Pytester, tmp_path: Path):
    pytester.makeini("[pytest]\nasyncio_mode = auto\n")
    pytester.makefile(
        ".yaml",
        **{"tests/evals/simple": ("id: simple_test\nthreshold: 0.0\nruns: 1\nturns:\n  - user: hi\n")},
    )
    pytester.makeconftest(
        """
        import pytest
        @pytest.fixture
        def llm_eval_agent():
            async def agent(history):
                return "ok", []
            return agent
        """
    )
    report_path = tmp_path / "report.md"
    pytester.runpytest("--agent-eval-live", f"--agent-eval-report={report_path}")
    assert report_path.exists()
    content = report_path.read_text()
    assert "simple_test" in content


def test_verbose_output_shows_run_details(pytester: pytest.Pytester):
    pytester.makeini("[pytest]\nasyncio_mode = auto\n")
    pytester.makefile(
        ".yaml",
        **{"tests/evals/verbose_test": ("id: verbose_case\nthreshold: 0.0\nruns: 1\nturns:\n  - user: hi\n")},
    )
    pytester.makeconftest(
        """
        import pytest
        @pytest.fixture
        def llm_eval_agent():
            async def agent(history):
                return "ok", []
            return agent
        """
    )
    result = pytester.runpytest("--agent-eval-live", "-v")
    result.stdout.fnmatch_lines(["*verbose_case*"])


def _make_mock_config(*, has_workerinput: bool = False, dist: str = "no") -> Any:
    cfg = types.SimpleNamespace()
    cfg.option = types.SimpleNamespace(dist=dist)
    if has_workerinput:
        cfg.workerinput = {}
    return cfg


def test_is_xdist_worker_when_workerinput_present():
    cfg = _make_mock_config(has_workerinput=True, dist="load")
    plugin = AgentEvalReportPlugin(cfg)
    assert plugin._is_xdist_worker() is True


def test_is_not_xdist_worker_normally():
    cfg = _make_mock_config()
    plugin = AgentEvalReportPlugin(cfg)
    assert plugin._is_xdist_worker() is False


def test_is_xdist_controller_when_dist_active_and_not_worker():
    cfg = _make_mock_config(dist="load")
    plugin = AgentEvalReportPlugin(cfg)
    assert plugin._is_xdist_controller() is True


def test_is_not_xdist_controller_when_dist_no():
    cfg = _make_mock_config(dist="no")
    plugin = AgentEvalReportPlugin(cfg)
    assert plugin._is_xdist_controller() is False


def test_logreport_collects_result_on_controller():
    cfg = _make_mock_config(dist="load")
    plugin = AgentEvalReportPlugin(cfg)
    result = _make_full_result()

    report = types.SimpleNamespace(
        when="call",
        nodeid="tests/evals/foo.yaml::my_transcript",
        failed=False,
        outcome="passed",
        user_properties=[
            ("llm_eval_name", "my_transcript"),
            ("llm_eval_result", _serialize_result(result)),
        ],
    )
    plugin.pytest_runtest_logreport(report)

    assert len(plugin._results) == 1
    name, collected = plugin._results[0]
    assert name == "my_transcript"
    assert collected == result


def test_logreport_ignores_non_call_phases():
    cfg = _make_mock_config(dist="load")
    plugin = AgentEvalReportPlugin(cfg)

    for phase in ("setup", "teardown"):
        report = types.SimpleNamespace(
            when=phase, nodeid="foo::bar", failed=False, outcome="passed", user_properties=[]
        )
        plugin.pytest_runtest_logreport(report)

    assert plugin._results == []


def test_xdist_active_returns_false_when_no_dist_option():
    cfg = types.SimpleNamespace()
    # config.option does not have a 'dist' attribute
    cfg.option = types.SimpleNamespace()
    plugin = AgentEvalReportPlugin(cfg)
    assert plugin._xdist_active() is False


def test_logreport_ignores_reports_without_llm_eval_result():
    cfg = _make_mock_config(dist="load")
    plugin = AgentEvalReportPlugin(cfg)
    report = types.SimpleNamespace(
        when="call",
        nodeid="tests/foo.yaml::bar",
        failed=False,
        outcome="passed",
        user_properties=[("some_other_key", "value")],
    )
    plugin.pytest_runtest_logreport(report)
    assert plugin._results == []


def _meta(identity: str, tags: list[str] | None = None, markers: list[str] | None = None) -> dict:
    return {"identity": identity, "tags": tags or [], "markers": markers or []}


def test_record_outcome_phase_state_machine():
    plugin = AgentEvalReportPlugin(_make_mock_config())

    plugin._record_outcome("n1", _meta("t1"), "setup", "passed")
    plugin._record_outcome("n1", _meta("t1"), "call", "passed")
    plugin._record_outcome("n1", _meta("t1"), "teardown", "passed")
    assert plugin._outcomes["n1"].outcome == "passed"

    plugin._record_outcome("n2", _meta("t2"), "setup", "skipped")
    plugin._record_outcome("n2", _meta("t2"), "teardown", "passed")
    assert plugin._outcomes["n2"].outcome == "skipped"

    plugin._record_outcome("n3", _meta("t3"), "setup", "passed")
    plugin._record_outcome("n3", _meta("t3"), "call", "failed")
    assert plugin._outcomes["n3"].outcome == "failed"

    plugin._record_outcome("n4", _meta("t4"), "setup", "passed")
    plugin._record_outcome("n4", _meta("t4"), "call", "passed")
    plugin._record_outcome("n4", _meta("t4"), "teardown", "failed")
    assert plugin._outcomes["n4"].outcome == "failed"


def test_controller_replays_outcomes_from_user_properties():
    plugin = AgentEvalReportPlugin(_make_mock_config(dist="load"))
    meta = _meta("transcript_x", tags=["gate:x"])

    for when, outcome_str in (("setup", "passed"), ("call", "failed"), ("teardown", "passed")):
        report = types.SimpleNamespace(
            when=when,
            nodeid="tests/evals/x.yaml::transcript_x",
            failed=outcome_str == "failed",
            outcome=outcome_str,
            user_properties=[("llm_eval_meta", meta)],
        )
        plugin.pytest_runtest_logreport(report)

    entry = plugin._outcomes["tests/evals/x.yaml::transcript_x"]
    assert entry.outcome == "failed"
    assert entry.tags == ["gate:x"]
    assert "tests/evals/x.yaml::transcript_x" in plugin._failed_nodeids


def test_collect_error_flag_set():
    plugin = AgentEvalReportPlugin(_make_mock_config())
    plugin.pytest_collectreport(types.SimpleNamespace(failed=True))
    assert plugin._had_collect_error is True


def test_xdist_report_collects_all_workers(pytester: pytest.Pytester, tmp_path: Path):
    """With -n2, results from both workers appear in the report."""
    pytest.importorskip("xdist")
    pytester.makeini("[pytest]\nasyncio_mode = auto\n")
    pytester.makefile(
        ".yaml",
        **{
            "tests/evals/t1": "id: transcript_one\nthreshold: 0.0\nruns: 1\nturns:\n  - user: hi\n",
            "tests/evals/t2": "id: transcript_two\nthreshold: 0.0\nruns: 1\nturns:\n  - user: hello\n",
        },
    )
    pytester.makeconftest(
        """
        import pytest
        @pytest.fixture
        def llm_eval_agent():
            async def agent(history):
                return "ok", []
            return agent
        """
    )
    report_path = tmp_path / "xdist_report.md"
    result = pytester.runpytest("--agent-eval-live", f"--agent-eval-report={report_path}", "-n2")
    result.assert_outcomes(passed=2)
    assert report_path.exists()
    content = report_path.read_text()
    assert content.count("transcript_one") == 2
    assert content.count("transcript_two") == 2
