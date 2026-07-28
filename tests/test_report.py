import json
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
from tests.helpers.pytester_project import EvalProject, static_agent


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


def test_serialize_result_produces_dict() -> None:
    result = _make_full_result()
    data = _serialize_result(result)
    assert isinstance(data, dict)
    assert data["passed"] is True
    assert data["score"] == 0.75
    assert len(data["runs"]) == 2


def test_deserialize_result_roundtrip() -> None:
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


def test_build_markdown_report_contains_summary_table() -> None:
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


def test_build_markdown_report_shows_score() -> None:
    results = [_make_result(True, 0.75, 0.5, "test_score")]
    report = build_markdown_report(results)
    assert "0.75" in report
    assert "0.50" in report


def test_report_written_to_file_with_flag(pytester: pytest.Pytester, tmp_path: Path) -> None:
    EvalProject(
        conftest=static_agent(),
        transcripts={"tests/evals/simple": "id: simple_test\nthreshold: 0.0\nruns: 1\nturns:\n  - user: hi\n"},
    ).write(pytester)
    report_path = tmp_path / "report.md"
    pytester.runpytest("--agent-eval-live", f"--agent-eval-report={report_path}")
    assert report_path.exists()
    content = report_path.read_text()
    assert "simple_test" in content


def test_verbose_output_shows_run_details(pytester: pytest.Pytester) -> None:
    EvalProject(
        conftest=static_agent(),
        transcripts={"tests/evals/verbose_test": "id: verbose_case\nthreshold: 0.0\nruns: 1\nturns:\n  - user: hi\n"},
    ).write(pytester)
    result = pytester.runpytest("--agent-eval-live", "-v")
    result.stdout.fnmatch_lines(["*verbose_case*"])


def _make_mock_config(*, has_workerinput: bool = False, dist: str = "no", verbose: int = 0) -> Any:
    cfg = types.SimpleNamespace()
    cfg.option = types.SimpleNamespace(dist=dist)
    cfg.getoption = lambda name, default=None: verbose if name == "verbose" else default
    if has_workerinput:
        cfg.workerinput = {}
    return cfg


# --- the xdist worker path, driven in-process ---
#
# These branches only ever execute inside an xdist *worker subprocess*, which the
# coverage run cannot see: the three -n2 tests pass while these very lines record as
# never executed. They are the riskiest lines in the module and so must be exercised
# directly, not vicariously through a subprocess that coverage is blind to.


class _FakeItem:
    """Minimal stand-in for a pytest.Item as the report plugin consumes one."""

    def __init__(self, name: str, *, tags: list[str] | None = None, markers: list[str] | None = None) -> None:
        self.name = name
        self.nodeid = f"tests/evals/{name}.yaml::{name}"
        self._tags = tags or []
        self._markers = markers or []

    def get_closest_marker(self, name: str) -> Any:
        if name == "agent_eval":
            return types.SimpleNamespace(kwargs={"tags": self._tags})
        return None

    def iter_markers(self) -> list[Any]:
        return [types.SimpleNamespace(name=m) for m in self._markers]


class _FakeReport:
    """Minimal stand-in for a pytest.TestReport with the mutable buffers the plugin writes."""

    def __init__(self, when: str = "call", outcome: str = "passed") -> None:
        self.when = when
        self.outcome = outcome
        self.failed = outcome == "failed"
        self.user_properties: list[tuple[str, Any]] = []
        self.sections: list[tuple[str, str]] = []


def _drive_makereport(plugin: AgentEvalReportPlugin, item: Any, report: _FakeReport, when: str = "call") -> _FakeReport:
    """Run the makereport hookwrapper to completion in-process."""
    gen = plugin.pytest_runtest_makereport(item=item, call=types.SimpleNamespace(when=when))
    next(gen)
    try:
        gen.send(types.SimpleNamespace(get_result=lambda: report))
    except StopIteration:
        pass
    return report


def _worker_plugin(*, groups: list[Any] | None = None, verbose: int = 0) -> AgentEvalReportPlugin:
    from pytest_agent_eval.config import AgentEvalConfig

    plugin = AgentEvalReportPlugin(_make_mock_config(has_workerinput=True, dist="load", verbose=verbose))
    # Seed the memo directly: load_config() would need a real pytest Config with a rootdir.
    plugin._cfg = AgentEvalConfig(groups=groups or [])
    return plugin


def test_worker_forwards_name_and_result_through_user_properties() -> None:
    """The worker cannot reach the controller's buffers, so results ride user_properties."""
    plugin = _worker_plugin()
    item = _FakeItem("transcript_one")
    item._eval_result = _make_full_result()

    report = _drive_makereport(plugin, item, _FakeReport())

    forwarded = dict(report.user_properties)
    assert forwarded["llm_eval_name"] == "transcript_one"
    assert _deserialize_result(forwarded["llm_eval_result"]) == _make_full_result()
    # A worker must not also collect locally, or the controller would double-count.
    assert plugin._results == []


def test_worker_forwards_group_meta_once_across_phases() -> None:
    """user_properties is shared across phases, so the append must be idempotent."""
    from pytest_agent_eval.groups import GroupConfig

    plugin = _worker_plugin(groups=[GroupConfig(name="g", tags=["gate:x"])])
    item = _FakeItem("transcript_one", tags=["gate:x"], markers=["agent_eval"])
    report = _FakeReport()

    for when in ("setup", "call", "teardown"):
        report.when = when
        _drive_makereport(plugin, item, report, when=when)

    metas = [v for k, v in report.user_properties if k == "llm_eval_meta"]
    assert len(metas) == 1
    assert metas[0] == {"identity": "transcript_one", "tags": ["gate:x"], "markers": ["agent_eval"]}


def test_worker_omits_group_meta_when_no_groups_configured() -> None:
    """Gated on groups so junitxml is not polluted for the majority who do not use them."""
    plugin = _worker_plugin(groups=[])
    report = _drive_makereport(plugin, _FakeItem("t", tags=["gate:x"]), _FakeReport())
    assert [k for k, _ in report.user_properties if k == "llm_eval_meta"] == []


def test_xdist_wire_payloads_are_json_serialisable() -> None:
    """Xdist ships user_properties through JSON; a non-JSON value breaks worker runs."""
    plugin = _worker_plugin()
    item = _FakeItem("transcript_one", tags=["gate:x"], markers=["agent_eval"])
    item._eval_result = _make_full_result()

    json.dumps(AgentEvalReportPlugin._item_meta(item))
    json.dumps(_serialize_result(_make_full_result()))
    json.dumps(dict(_drive_makereport(plugin, item, _FakeReport()).user_properties))


def test_controller_collects_locally_instead_of_forwarding() -> None:
    plugin = AgentEvalReportPlugin(_make_mock_config())
    item = _FakeItem("transcript_one")
    item._eval_result = _make_full_result()

    report = _drive_makereport(plugin, item, _FakeReport())

    assert report.user_properties == []
    assert plugin._results == [("transcript_one", _make_full_result())]


def test_makereport_records_failures_and_skips_non_call_phases() -> None:
    plugin = AgentEvalReportPlugin(_make_mock_config())
    item = _FakeItem("transcript_one")

    _drive_makereport(plugin, item, _FakeReport(when="setup", outcome="failed"), when="setup")

    assert item.nodeid in plugin._failed_nodeids
    assert plugin._results == []


def test_verbose_detail_section_lists_runs_and_reasoning() -> None:
    """-v lists each run; -vv adds every evaluator's reasoning under it."""
    plugin = AgentEvalReportPlugin(_make_mock_config(verbose=2))
    item = _FakeItem("transcript_one")
    item._eval_result = _make_full_result()

    report = _drive_makereport(plugin, item, _FakeReport())

    title, body = report.sections[0]
    assert title == "LLM Eval"
    assert "Run 1 ✅" in body
    assert "Run 2 ❌" in body
    assert "looks good" in body
    assert "missing keyword" in body


def test_verbose_level_one_omits_per_turn_reasoning() -> None:
    plugin = AgentEvalReportPlugin(_make_mock_config(verbose=1))
    item = _FakeItem("transcript_one")
    item._eval_result = _make_full_result()

    _, body = _drive_makereport(plugin, item, _FakeReport()).sections[0]

    assert "Run 1 ✅" in body
    assert "looks good" not in body


def test_no_detail_section_without_verbosity() -> None:
    plugin = AgentEvalReportPlugin(_make_mock_config(verbose=0))
    item = _FakeItem("transcript_one")
    item._eval_result = _make_full_result()
    assert _drive_makereport(plugin, item, _FakeReport()).sections == []


def test_is_xdist_worker_when_workerinput_present() -> None:
    cfg = _make_mock_config(has_workerinput=True, dist="load")
    plugin = AgentEvalReportPlugin(cfg)
    assert plugin._is_xdist_worker() is True


def test_is_not_xdist_worker_normally() -> None:
    cfg = _make_mock_config()
    plugin = AgentEvalReportPlugin(cfg)
    assert plugin._is_xdist_worker() is False


def test_is_xdist_controller_when_dist_active_and_not_worker() -> None:
    cfg = _make_mock_config(dist="load")
    plugin = AgentEvalReportPlugin(cfg)
    assert plugin._is_xdist_controller() is True


def test_is_not_xdist_controller_when_dist_no() -> None:
    cfg = _make_mock_config(dist="no")
    plugin = AgentEvalReportPlugin(cfg)
    assert plugin._is_xdist_controller() is False


def test_logreport_collects_result_on_controller() -> None:
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


def test_logreport_ignores_non_call_phases() -> None:
    cfg = _make_mock_config(dist="load")
    plugin = AgentEvalReportPlugin(cfg)

    for phase in ("setup", "teardown"):
        report = types.SimpleNamespace(
            when=phase, nodeid="foo::bar", failed=False, outcome="passed", user_properties=[]
        )
        plugin.pytest_runtest_logreport(report)

    assert plugin._results == []


def test_xdist_active_returns_false_when_no_dist_option() -> None:
    cfg = types.SimpleNamespace()
    # config.option does not have a 'dist' attribute
    cfg.option = types.SimpleNamespace()
    plugin = AgentEvalReportPlugin(cfg)
    assert plugin._xdist_active() is False


def test_logreport_ignores_reports_without_llm_eval_result() -> None:
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


def test_record_outcome_phase_state_machine() -> None:
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


def test_controller_replays_outcomes_from_user_properties() -> None:
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


def test_collect_error_flag_set() -> None:
    plugin = AgentEvalReportPlugin(_make_mock_config())
    plugin.pytest_collectreport(types.SimpleNamespace(failed=True))
    assert plugin._had_collect_error is True


def test_xdist_report_collects_all_workers(pytester: pytest.Pytester, tmp_path: Path) -> None:
    """With -n2, results from both workers appear in the report."""
    pytest.importorskip("xdist")
    EvalProject(
        conftest=static_agent(),
        transcripts={
            "tests/evals/t1": "id: transcript_one\nthreshold: 0.0\nruns: 1\nturns:\n  - user: hi\n",
            "tests/evals/t2": "id: transcript_two\nthreshold: 0.0\nruns: 1\nturns:\n  - user: hello\n",
        },
    ).write(pytester)
    report_path = tmp_path / "xdist_report.md"
    result = pytester.runpytest("--agent-eval-live", f"--agent-eval-report={report_path}", "-n2")
    result.assert_outcomes(passed=2)
    assert report_path.exists()
    content = report_path.read_text()
    assert content.count("transcript_one") == 2
    assert content.count("transcript_two") == 2


def test_verbose_detail_omits_evaluators_that_gave_no_reasoning() -> None:
    """Deterministic evaluators can pass with an empty reasoning; that must not print a blank line."""
    plugin = AgentEvalReportPlugin(_make_mock_config(verbose=2))
    item = _FakeItem("transcript_one")
    item._eval_result = TranscriptResult(
        passed=True,
        score=1.0,
        threshold=0.5,
        runs=[
            RunResult(
                run_index=0,
                passed=True,
                turn_results=[
                    TurnResult(
                        turn_index=0,
                        passed=True,
                        eval_results=[EvalResult(passed=True, reasoning=""), EvalResult(passed=True, reasoning="kept")],
                    )
                ],
            )
        ],
    )

    _, body = _drive_makereport(plugin, item, _FakeReport()).sections[0]

    assert "kept" in body
    assert "\n    \n" not in body
