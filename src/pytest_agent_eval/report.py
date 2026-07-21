"""Terminal output hooks and markdown report writer."""

from __future__ import annotations

import dataclasses
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from pytest_agent_eval.groups import (
    EvalOutcome,
    GroupResult,
    build_group_markdown_lines,
    evaluate_groups,
    format_group_summary_lines,
)
from pytest_agent_eval.models import EvalResult, RunResult, TranscriptResult, TurnResult


def _serialize_result(result: TranscriptResult) -> dict[str, Any]:
    return dataclasses.asdict(result)


def _deserialize_run(r: dict[str, Any]) -> RunResult:
    return RunResult(
        run_index=r["run_index"],
        passed=r["passed"],
        turn_results=[
            TurnResult(
                turn_index=t["turn_index"],
                passed=t["passed"],
                eval_results=[EvalResult(passed=e["passed"], reasoning=e["reasoning"]) for e in t["eval_results"]],
            )
            for t in r["turn_results"]
        ],
    )


def _deserialize_result(data: dict[str, Any]) -> TranscriptResult:
    return TranscriptResult(
        passed=data["passed"],
        score=data["score"],
        threshold=data["threshold"],
        runs=[_deserialize_run(r) for r in data["runs"]],
    )


def build_markdown_report(
    results: list[tuple[str, TranscriptResult]],
    run_date: str | None = None,
    group_results: list[GroupResult] | None = None,
) -> str:
    """Build a markdown evaluation report from a list of (name, result) pairs.

    Args:
        results: List of (transcript_id, TranscriptResult) pairs.
        run_date: Optional date string for the report header.
        group_results: Optional group aggregation results for a Groups section.

    Returns:
        Formatted markdown string.
    """
    today = run_date or date.today().isoformat()
    lines = [f"# LLM Eval Report — {today}", "", "## Summary", ""]
    lines.append("| Transcript | Runs | Passed | Score | Threshold | Status |")
    lines.append("|---|---|---|---|---|---|")

    for name, result in results:
        status = "✅ PASS" if result.passed else "❌ FAIL"
        n, p = len(result.runs), result.passed_run_count
        lines.append(f"| {name} | {n} | {p} | {result.score:.2f} | {result.threshold:.2f} | {status} |")

    if group_results:
        lines.append("")
        lines.extend(build_group_markdown_lines(group_results))

    lines.append("")
    lines.append("## Details")
    lines.append("")

    for name, result in results:
        lines.append(f"### {name}")
        for run in result.runs:
            lines.extend(_format_run_lines(run))
        lines.append("")

    return "\n".join(lines)


def _format_run_lines(run: Any) -> list[str]:
    lines = [f"**Run {run.run_index + 1}** {'✅' if run.passed else '❌'}"]
    for turn in run.turn_results:
        lines.append(f"- Turn {turn.turn_index + 1}: {'PASS' if turn.passed else 'FAIL'}")
        lines.extend(f"  - {er.reasoning}" for er in turn.eval_results if er.reasoning)
    return lines


def _score_line(result: TranscriptResult) -> str:
    symbol = ">=" if result.passed else "<"
    p, n = result.passed_run_count, len(result.runs)
    return f"[{p}/{n} runs, score={result.score:.2f} {symbol} {result.threshold:.2f}]"


_XDIST_RESULT_KEY = "llm_eval_result"
_XDIST_NAME_KEY = "llm_eval_name"
_XDIST_META_KEY = "llm_eval_meta"


class AgentEvalReportPlugin:
    """Pytest plugin that collects results and writes the report."""

    def __init__(self, config: pytest.Config) -> None:
        """Bind the plugin to a pytest config and initialise the result buffers."""
        self._config = config
        self._results: list[tuple[str, TranscriptResult]] = []
        self._outcomes: dict[str, EvalOutcome] = {}
        self._failed_nodeids: set[str] = set()
        self._had_collect_error = False
        self._deselected_count = 0
        self._exit_overridden = False
        self._cfg: Any = None

    def _get_cfg(self) -> Any:
        if self._cfg is None:
            from pytest_agent_eval.config import load_config

            self._cfg = load_config(self._config)
        return self._cfg

    @staticmethod
    def _item_meta(item: pytest.Item) -> dict[str, Any]:
        marker = item.get_closest_marker("agent_eval")
        tags = list((marker.kwargs.get("tags") if marker else None) or [])
        return {"identity": item.name, "tags": tags, "markers": [m.name for m in item.iter_markers()]}

    def _record_outcome(self, nodeid: str, meta: dict[str, Any], when: str, outcome: str) -> None:
        entry = self._outcomes.get(nodeid)
        if entry is None:
            entry = EvalOutcome(
                identity=meta["identity"],
                nodeid=nodeid,
                outcome="passed",
                tags=list(meta["tags"]),
                markers=list(meta["markers"]),
            )
            self._outcomes[nodeid] = entry
        if when == "setup":
            if outcome in ("skipped", "failed"):
                entry.outcome = outcome
        elif when == "call":
            entry.outcome = outcome
        elif when == "teardown" and outcome == "failed" and entry.outcome == "passed":
            entry.outcome = "failed"

    def add_result(self, name: str, result: TranscriptResult) -> None:
        """Append a transcript result to the in-memory report buffer."""
        self._results.append((name, result))

    def _is_xdist_worker(self) -> bool:
        return hasattr(self._config, "workerinput")

    def _xdist_active(self) -> bool:
        try:
            return self._config.option.dist != "no"
        except AttributeError:
            return False

    def _is_xdist_controller(self) -> bool:
        return self._xdist_active() and not self._is_xdist_worker()

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_makereport(self, item: pytest.Item, call: pytest.CallInfo) -> Any:
        """Capture per-test eval results and outcomes, forwarding across xdist workers."""
        outcome = yield
        report = outcome.get_result()

        meta = self._item_meta(item)
        if self._is_xdist_worker():
            # user_properties is shared across phases, so the setup-phase append rides
            # every report; gate on groups so junitxml isn't polluted for non-users.
            if self._get_cfg().groups and not any(k == _XDIST_META_KEY for k, _ in report.user_properties):
                report.user_properties.append((_XDIST_META_KEY, meta))
        else:
            self._record_outcome(item.nodeid, meta, report.when, report.outcome)
            if report.failed:
                self._failed_nodeids.add(item.nodeid)

        if call.when == "call":
            result: TranscriptResult | None = getattr(item, "_eval_result", None)
            if result is not None:
                if self._is_xdist_worker():
                    report.user_properties.append((_XDIST_NAME_KEY, item.name))
                    report.user_properties.append((_XDIST_RESULT_KEY, _serialize_result(result)))
                else:
                    self.add_result(item.name, result)
                score_info = _score_line(result)
                verbosity = self._config.getoption("verbose", default=0)
                if verbosity >= 1:
                    details = []
                    for run in result.runs:
                        run_status = "✅" if run.passed else "❌"
                        details.append(f"  Run {run.run_index + 1} {run_status}")
                        if verbosity >= 2:
                            for turn in run.turn_results:
                                for er in turn.eval_results:
                                    if er.reasoning:
                                        details.append(f"    {er.reasoning}")
                    report.sections.append(("LLM Eval", f"{score_info}\n" + "\n".join(details)))

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        """On the xdist controller, replay outcomes and deserialise forwarded eval results."""
        if not self._is_xdist_controller():
            return

        if report.failed:
            self._failed_nodeids.add(report.nodeid)
        meta = next((v for k, v in report.user_properties if k == _XDIST_META_KEY), None)
        if meta is not None:
            self._record_outcome(report.nodeid, meta, report.when, report.outcome)

        if report.when != "call":
            return
        result_data = next((v for k, v in report.user_properties if k == _XDIST_RESULT_KEY), None)
        if result_data is None:
            return
        name = next((v for k, v in report.user_properties if k == _XDIST_NAME_KEY), report.nodeid)
        self.add_result(name, _deserialize_result(result_data))

    def pytest_collectreport(self, report: pytest.CollectReport) -> None:
        """Remember collection errors — they veto any exit-code override."""
        if report.failed:
            self._had_collect_error = True

    def pytest_deselected(self, items: Any) -> None:
        """Track deselection so the group summary can flag partial selections."""
        self._deselected_count += len(items)

    def _group_results(self) -> list[GroupResult]:
        return evaluate_groups(self._get_cfg().groups, list(self._outcomes.values()))

    def pytest_terminal_summary(self, terminalreporter: Any) -> None:
        """Render the group summary section after the run."""
        cfg = self._get_cfg()
        if not cfg.groups or not self._outcomes:
            return
        terminalreporter.section("group summary")
        for line in format_group_summary_lines(self._group_results()):
            terminalreporter.write_line(line, yellow="WARNING" in line)
        if self._deselected_count:
            terminalreporter.write_line(
                f"note: {self._deselected_count} test(s) deselected — group pass rates reflect the selected subset"
            )
        if self._exit_overridden:
            terminalreporter.write_line("exit code overridden to 0: all group thresholds met", green=True)

    def pytest_sessionfinish(self, session: pytest.Session, exitstatus: int) -> None:
        """Write the markdown report and apply the group exit-code override."""
        cfg = self._get_cfg()
        if cfg.report_path and self._results:
            group_results = self._group_results() if cfg.groups else None
            report_text = build_markdown_report(self._results, group_results=group_results)
            Path(cfg.report_path).write_text(report_text)
        self._maybe_override_exit_code(session, exitstatus)

    def _maybe_override_exit_code(self, session: pytest.Session, exitstatus: int) -> None:
        # Only downgrade TESTS_FAILED to OK, and only when every failure is absorbed
        # by a passing gated group — a failing plain unit test, an ungrouped
        # transcript, or a collection error must keep the red exit code.
        if not self._get_cfg().groups or exitstatus != pytest.ExitCode.TESTS_FAILED or self._had_collect_error:
            return
        results = self._group_results()
        # A failed must_pass assertion vetoes the override even when the group's
        # selectors matched nothing (a selector-less must_pass-only gate has total == 0).
        if any(r.must_pass_failed for r in results):
            return
        gated = [r for r in results if r.total > 0]
        if not gated or any(not r.passed for r in gated):
            return
        covered_failed = {nodeid for result in gated for nodeid in result.failed_nodeids}
        if not self._failed_nodeids.issubset(covered_failed):
            return
        session.exitstatus = pytest.ExitCode.OK
        self._exit_overridden = True
