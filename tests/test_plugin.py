"""Integration tests for plugin.py using pytester."""
import pytest


def test_plugin_registers_marker(pytester: pytest.Pytester):
    result = pytester.runpytest("--markers")
    result.stdout.fnmatch_lines(["*llm_eval*"])


def test_llm_eval_tests_skipped_by_default(pytester: pytest.Pytester):
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.llm_eval
        async def test_something(llm_eval):
            pass
        """
    )
    result = pytester.runpytest("-v")
    result.stdout.fnmatch_lines(["*test_something*SKIPPED*"])
    assert result.ret == 0


def test_llm_eval_tests_run_with_live_flag(pytester: pytest.Pytester):
    pytester.makeini("[pytest]\nasyncio_mode = auto\n")
    pytester.makepyfile(
        """
        import pytest
        from pytest_llm_eval.models import Turn

        async def _agent(history):
            return "hello", []

        @pytest.mark.llm_eval(threshold=0.0, runs=1)
        async def test_something(llm_eval):
            result = await llm_eval.run(agent=_agent, turns=[Turn(user="hi")])
            result.assert_threshold()
        """
    )
    result = pytester.runpytest("--llm-eval-live", "-v")
    result.stdout.fnmatch_lines(["*test_something*PASSED*"])
    assert result.ret == 0


def test_llm_eval_runs_with_eval_live_env(pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("EVAL_LIVE", "1")
    pytester.makeini("[pytest]\nasyncio_mode = auto\n")
    pytester.makepyfile(
        """
        import pytest
        from pytest_llm_eval.models import Turn

        async def _agent(history):
            return "ok", []

        @pytest.mark.llm_eval(threshold=0.0)
        async def test_env(llm_eval):
            result = await llm_eval.run(agent=_agent, turns=[Turn(user="hi")])
            result.assert_threshold()
        """
    )
    result = pytester.runpytest("-v")
    result.stdout.fnmatch_lines(["*test_env*PASSED*"])


def test_marker_threshold_overrides_config(pytester: pytest.Pytester):
    pytester.makeini("[pytest]\nasyncio_mode = auto\n")
    pytester.makepyfile(
        """
        import pytest
        from pytest_llm_eval.models import Turn

        async def _agent(history):
            return "nope", []

        @pytest.mark.llm_eval(threshold=0.0, runs=1)
        async def test_always_passes(llm_eval):
            result = await llm_eval.run(
                agent=_agent,
                turns=[Turn(user="hi")],
            )
            result.assert_threshold()
        """
    )
    result = pytester.runpytest("--llm-eval-live", "-v")
    assert result.ret == 0


def test_cli_options_exist(pytester: pytest.Pytester):
    result = pytester.runpytest("--help")
    result.stdout.fnmatch_lines(["*--llm-eval-live*"])
    result.stdout.fnmatch_lines(["*--llm-eval-report*"])
