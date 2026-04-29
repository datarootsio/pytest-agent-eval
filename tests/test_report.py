from pathlib import Path

import pytest

from pytest_llm_eval.models import EvalResult, RunResult, TranscriptResult, TurnResult
from pytest_llm_eval.report import build_markdown_report


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
    pytester.runpytest("--llm-eval-live", f"--llm-eval-report={report_path}")
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
    result = pytester.runpytest("--llm-eval-live", "-v")
    result.stdout.fnmatch_lines(["*verbose_case*"])
