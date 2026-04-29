"""Terminal output hooks and markdown report writer."""

from __future__ import annotations

import dataclasses
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from pytest_llm_eval.models import EvalResult, RunResult, TranscriptResult, TurnResult


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
) -> str:
    """Build a markdown evaluation report from a list of (name, result) pairs.

    Args:
        results: List of (transcript_id, TranscriptResult) pairs.
        run_date: Optional date string for the report header.

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


class LLMEvalReportPlugin:
    """Pytest plugin that collects results and writes the report."""

    def __init__(self, config: pytest.Config) -> None:
        self._config = config
        self._results: list[tuple[str, TranscriptResult]] = []

    def add_result(self, name: str, result: TranscriptResult) -> None:
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
        outcome = yield
        report = outcome.get_result()
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
        if not self._is_xdist_controller() or report.when != "call":
            return
        result_data = next((v for k, v in report.user_properties if k == _XDIST_RESULT_KEY), None)
        if result_data is None:
            return
        name = next((v for k, v in report.user_properties if k == _XDIST_NAME_KEY), report.nodeid)
        self.add_result(name, _deserialize_result(result_data))

    def pytest_sessionfinish(self, session: pytest.Session, exitstatus: int) -> None:
        from pytest_llm_eval.config import load_config

        cfg = load_config(self._config)
        if cfg.report_path and self._results:
            report_text = build_markdown_report(self._results)
            Path(cfg.report_path).write_text(report_text)
