"""Terminal output hooks and markdown report writer."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from pydantic import TypeAdapter

from pytest_agent_eval.groups import (
    EvalOutcome,
    GroupResult,
    build_group_markdown_lines,
    evaluate_groups,
    format_group_summary_lines,
)
from pytest_agent_eval.models import JsonMapping, RunResult, TranscriptResult

if TYPE_CHECKING:
    from collections.abc import Generator, Sequence

    from pluggy import Result

    from pytest_agent_eval.config import AgentEvalConfig


# One adapter for the whole tree. TypeAdapter works on dataclasses, so the result types
# stay plain frozen records rather than becoming pydantic models just to cross a process.
_RESULT_WIRE: TypeAdapter[TranscriptResult] = TypeAdapter(TranscriptResult)


def _serialize_result(result: TranscriptResult) -> JsonMapping:
    """Flatten a result for the xdist user_properties channel.

    mode="json" because xdist ships user_properties through JSON; anything that is not
    JSON-native here fails inside a worker with a confusing traceback.
    """
    return _RESULT_WIRE.dump_python(result, mode="json")


def _deserialize_result(data: JsonMapping) -> TranscriptResult:
    """Rebuild a result the controller received from a worker.

    Validated rather than hand-unpacked: the previous three-function walk had to be kept
    in step with the record definitions by hand, and could not be type-checked because
    every level indexed into a JsonValue.
    """
    return _RESULT_WIRE.validate_python(data)


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
    # UTC, not local: a report's date must not depend on the runner's timezone.
    today = run_date or datetime.now(tz=UTC).date().isoformat()
    lines = [f"# LLM Eval Report — {today}", "", "## Summary", ""]
    lines.append("| Transcript | Runs | Passed | Score | Threshold | Status |")
    lines.append("|---|---|---|---|---|---|")

    for name, result in results:
        status = "✅ PASS" if result.passed else "❌ FAIL"
        passed, total = result.passed_run_count, len(result.runs)
        lines.append(f"| {name} | {total} | {passed} | {result.score:.2f} | {result.threshold:.2f} | {status} |")

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


def _format_run_lines(run: RunResult) -> list[str]:
    lines = [f"**Run {run.run_index + 1}** {'✅' if run.passed else '❌'}"]
    for turn in run.turn_results:
        lines.append(f"- Turn {turn.turn_index + 1}: {'PASS' if turn.passed else 'FAIL'}")
        lines.extend(f"  - {er.reasoning}" for er in turn.eval_results if er.reasoning)
    return lines


def _reasoning_lines(run: RunResult) -> list[str]:
    """Every non-empty evaluator reasoning for one run, indented under it."""
    return [f"    {er.reasoning}" for turn in run.turn_results for er in turn.eval_results if er.reasoning]


def _detail_section(result: TranscriptResult, verbosity: int) -> str | None:
    """Build the per-test detail block, or None when the run is not verbose enough.

    -v lists each run; -vv adds every evaluator's reasoning underneath it.
    """
    if verbosity < 1:
        return None
    lines: list[str] = []
    for run in result.runs:
        lines.append(f"  Run {run.run_index + 1} {'✅' if run.passed else '❌'}")
        if verbosity >= _VERBOSITY_WITH_REASONING:
            lines.extend(_reasoning_lines(run))
    return f"{_score_line(result)}\n" + "\n".join(lines)


def _score_line(result: TranscriptResult) -> str:
    symbol = ">=" if result.passed else "<"
    passed, total = result.passed_run_count, len(result.runs)
    return f"[{passed}/{total} runs, score={result.score:.2f} {symbol} {result.threshold:.2f}]"


def _advance_outcome(entry: EvalOutcome, when: str, outcome: str) -> EvalOutcome:
    """Fold one phase report into the item's recorded outcome.

    setup only downgrades (a skip or error there decides the item); call is
    authoritative; teardown can only turn a pass into a failure.
    """
    if when == "setup" and outcome in ("skipped", "failed"):
        return dataclasses.replace(entry, outcome=outcome)
    if when == "call":
        return dataclasses.replace(entry, outcome=outcome)
    if when == "teardown" and outcome == "failed" and entry.outcome == "passed":
        return dataclasses.replace(entry, outcome="failed")
    return entry


# -vv, not -v: reasoning is per evaluator and floods the output at -v.
_VERBOSITY_WITH_REASONING = 2

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

    @cached_property
    def _cfg(self) -> AgentEvalConfig:
        """Resolved [tool.agent_eval] config, loaded once per session.

        cached_property rather than a None sentinel: the sentinel also forced the attribute
        to be untyped, which silently switched off checking at all five call sites.
        """
        # Deferred: config imports groups, which would make this circular at module scope.
        from pytest_agent_eval.config import load_config  # noqa: PLC0415

        return load_config(self._config)

    @staticmethod
    def _item_meta(item: pytest.Item) -> JsonMapping:
        marker = item.get_closest_marker("agent_eval")
        tags = list((marker.kwargs.get("tags") if marker else None) or [])
        return {"identity": item.name, "tags": tags, "markers": [m.name for m in item.iter_markers()]}

    def _record_outcome(self, nodeid: str, meta: JsonMapping, when: str, outcome: str) -> None:
        entry = self._outcomes.get(nodeid) or EvalOutcome(
            identity=meta["identity"],
            nodeid=nodeid,
            outcome="passed",
            tags=list(meta["tags"]),
            markers=list(meta["markers"]),
        )
        self._outcomes[nodeid] = _advance_outcome(entry, when, outcome)

    @property
    def _is_worker(self) -> bool:
        """True on an xdist worker, which forwards results instead of buffering them.

        A property, not a method: it reads one attribute at three call sites, so the
        parentheses were the only thing it added.
        """
        return hasattr(self._config, "workerinput")

    def _xdist_active(self) -> bool:
        try:
            return self._config.option.dist != "no"
        except AttributeError:
            return False

    def _is_xdist_controller(self) -> bool:
        return self._xdist_active() and not self._is_worker

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_makereport(
        self, item: pytest.Item, call: pytest.CallInfo[None]
    ) -> Generator[None, Result[pytest.TestReport], None]:
        """Capture per-test eval results and outcomes, forwarding across xdist workers."""
        outcome = yield
        report = outcome.get_result()

        meta = self._item_meta(item)
        if self._is_worker:
            # user_properties is shared across phases, so the setup-phase append rides
            # every report; gate on groups so junitxml isn't polluted for non-users.
            if self._cfg.groups and not any(k == _XDIST_META_KEY for k, _ in report.user_properties):
                report.user_properties.append((_XDIST_META_KEY, meta))
        else:
            self._record_outcome(item.nodeid, meta, report.when, report.outcome)
            if report.failed:
                self._failed_nodeids.add(item.nodeid)

        if call.when == "call":
            result: TranscriptResult | None = getattr(item, "_eval_result", None)
            if result is not None:
                if self._is_worker:
                    report.user_properties.append((_XDIST_NAME_KEY, item.name))
                    report.user_properties.append((_XDIST_RESULT_KEY, _serialize_result(result)))
                else:
                    self._results.append((item.name, result))
                section = _detail_section(result, self._config.getoption("verbose", default=0))
                if section is not None:
                    report.sections.append(("LLM Eval", section))

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
        self._results.append((name, _deserialize_result(result_data)))

    def pytest_collectreport(self, report: pytest.CollectReport) -> None:
        """Remember collection errors — they veto any exit-code override."""
        if report.failed:
            self._had_collect_error = True

    def pytest_deselected(self, items: Sequence[pytest.Item]) -> None:
        """Track deselection so the group summary can flag partial selections."""
        self._deselected_count += len(items)

    def _group_results(self) -> list[GroupResult]:
        """Aggregate the session's outcomes into per-group results.

        A one-liner that stays a method, because it is not free: it re-runs
        evaluate_groups over every recorded outcome, and three call sites reach it per
        session. Inlining would triple that work at the call sites and hide the cost there.

        Deliberately not memoised. All three callers run at session end, after every
        runtest hook has recorded its outcome, so a cache would in fact be correct today —
        but nothing in the type or the name would stop a future caller being added mid-run,
        and that one would silently receive a stale outcome set. The recompute is bounded
        by the number of tests in the session and buys that immunity.
        """
        return evaluate_groups(self._cfg.groups, list(self._outcomes.values()))

    def pytest_terminal_summary(self, terminalreporter: pytest.TerminalReporter) -> None:
        """Render the group summary section after the run."""
        cfg = self._cfg
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
        cfg = self._cfg
        if cfg.report_path and self._results:
            group_results = self._group_results() if cfg.groups else None
            report_text = build_markdown_report(self._results, group_results=group_results)
            Path(cfg.report_path).write_text(report_text)
        self._maybe_override_exit_code(session, exitstatus)

    def _maybe_override_exit_code(self, session: pytest.Session, exitstatus: int) -> None:
        # Only downgrade TESTS_FAILED to OK, and only when every failure is absorbed
        # by a passing gated group — a failing plain unit test, an ungrouped
        # transcript, or a collection error must keep the red exit code.
        if not self._cfg.groups or exitstatus != pytest.ExitCode.TESTS_FAILED or self._had_collect_error:
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
