"""Every example project must keep passing; they run through pytester in-process.

In-process runpytest matters: the stub_judge monkeypatch reaches the runner's
lazily-imported JudgeEvaluator because example code executes in this process.
Do not switch to runpytest_subprocess.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def stub_judge(monkeypatch: pytest.MonkeyPatch):
    from pytest_agent_eval.evaluators.judge import JudgeEvaluator, ToolCallArgsJudgeEvaluator
    from pytest_agent_eval.models import EvalResult

    async def fake_evaluate(self, ctx):
        return EvalResult(passed=True, reasoning="stubbed judge (no API key in CI)")

    monkeypatch.setattr(JudgeEvaluator, "evaluate", fake_evaluate)
    monkeypatch.setattr(ToolCallArgsJudgeEvaluator, "evaluate", fake_evaluate)


def _run_example(pytester: pytest.Pytester, name: str, *args: str):
    pytester.copy_example(name)
    return pytester.runpytest("--agent-eval-live", *args)


def test_single_turn_example(pytester: pytest.Pytester):
    _run_example(pytester, "single-turn").assert_outcomes(passed=1)


def test_multi_turn_judge_example(pytester: pytest.Pytester, stub_judge: None):
    _run_example(pytester, "multi-turn-judge").assert_outcomes(passed=1)


def test_tool_calls_example(pytester: pytest.Pytester):
    _run_example(pytester, "tool-calls").assert_outcomes(passed=1)


def test_tool_call_args_example(pytester: pytest.Pytester, stub_judge: None):
    _run_example(pytester, "tool-call-args").assert_outcomes(passed=1)


def test_regex_contains_example(pytester: pytest.Pytester):
    _run_example(pytester, "regex-contains").assert_outcomes(passed=1)


def test_python_parametrize_example(pytester: pytest.Pytester):
    _run_example(pytester, "python-parametrize").assert_outcomes(passed=2)


def test_groups_example_absorbs_failure(pytester: pytest.Pytester):
    result = _run_example(pytester, "groups")
    result.assert_outcomes(passed=1, failed=1)
    assert result.ret == 0
    result.stdout.fnmatch_lines(
        [
            "*booking: 1/2 passed (50%) >= 50% required -- PASSED*",
            "*failures: booking_edge_case*",
            "*exit code overridden to 0*",
        ]
    )


def test_voice_livekit_example_collects(pytester: pytest.Pytester):
    pytester.copy_example("voice-livekit")
    result = pytester.runpytest("--collect-only", "-q")
    result.stdout.fnmatch_lines(["*booking_voice*"])


def test_example_skips_with_hint_without_live_flag(pytester: pytest.Pytester):
    pytester.copy_example("single-turn")
    result = pytester.runpytest()
    result.assert_outcomes(skipped=1)
    result.stdout.fnmatch_lines(["*1 eval test(s) skipped*live mode is off*"])
