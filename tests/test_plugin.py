"""Integration tests for plugin.py using pytester."""

from unittest.mock import AsyncMock, MagicMock

import pytest


def test_plugin_registers_marker(pytester: pytest.Pytester):
    result = pytester.runpytest("--markers")
    result.stdout.fnmatch_lines(["*agent_eval*"])


def test_llm_eval_tests_skipped_by_default(pytester: pytest.Pytester):
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.agent_eval
        async def test_something(agent_eval):
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
        from pytest_agent_eval.models import Turn

        async def _agent(history):
            return "hello", []

        @pytest.mark.agent_eval(threshold=0.0, runs=1)
        async def test_something(agent_eval):
            result = await agent_eval.run(agent=_agent, turns=[Turn(user="hi")])
            result.assert_threshold()
        """
    )
    result = pytester.runpytest("--agent-eval-live", "-v")
    result.stdout.fnmatch_lines(["*test_something*PASSED*"])
    assert result.ret == 0


def test_llm_eval_runs_with_eval_live_env(pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("EVAL_LIVE", "1")
    pytester.makeini("[pytest]\nasyncio_mode = auto\n")
    pytester.makepyfile(
        """
        import pytest
        from pytest_agent_eval.models import Turn

        async def _agent(history):
            return "ok", []

        @pytest.mark.agent_eval(threshold=0.0)
        async def test_env(agent_eval):
            result = await agent_eval.run(agent=_agent, turns=[Turn(user="hi")])
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
        from pytest_agent_eval.models import Turn

        async def _agent(history):
            return "nope", []

        @pytest.mark.agent_eval(threshold=0.0, runs=1)
        async def test_always_passes(agent_eval):
            result = await agent_eval.run(
                agent=_agent,
                turns=[Turn(user="hi")],
            )
            result.assert_threshold()
        """
    )
    result = pytester.runpytest("--agent-eval-live", "-v")
    assert result.ret == 0


def test_cli_options_exist(pytester: pytest.Pytester):
    result = pytester.runpytest("--help")
    result.stdout.fnmatch_lines(["*--agent-eval-live*"])
    result.stdout.fnmatch_lines(["*--agent-eval-report*"])


def test_marker_threshold_zero_is_honoured(pytester: pytest.Pytester):
    """threshold=0.0 must not fall back to config default (falsy trap)."""
    pytester.makeini("[pytest]\nasyncio_mode = auto\n")
    pytester.makepyfile(
        """
        import pytest
        from pytest_agent_eval.models import Turn
        from pytest_agent_eval.evaluators.contains import ContainsEvaluator

        async def _agent(history):
            return "wrong answer", []

        @pytest.mark.agent_eval(threshold=0.0, runs=1)
        async def test_zero_threshold(agent_eval):
            # ContainsEvaluator will fail, but threshold=0.0 means 0% must pass
            result = await agent_eval.run(
                agent=_agent,
                turns=[Turn(user="hi")],
            )
            result.assert_threshold()  # should NOT raise because threshold=0.0
        """
    )
    result = pytester.runpytest("--agent-eval-live", "-v")
    assert result.ret == 0


# --- Adapter tests ---


def test_pydantic_ai_adapter_normalises_output():
    from pytest_agent_eval.adapters.pydantic_ai import PydanticAIAdapter

    mock_agent = MagicMock()
    mock_result = MagicMock()
    mock_result.output = "Hello!"
    mock_result.all_messages.return_value = []
    mock_agent.run = AsyncMock(return_value=mock_result)

    adapter = PydanticAIAdapter(mock_agent)

    import asyncio

    reply, tool_calls = asyncio.run(adapter([{"role": "user", "content": "hi"}]))
    assert reply == "Hello!"
    assert tool_calls == []


def test_openai_adapter_normalises_output():
    from pytest_agent_eval.adapters.openai import OpenAIAdapter

    mock_client = MagicMock()
    mock_message = MagicMock()
    mock_message.content = "Hello from OpenAI!"
    mock_message.tool_calls = None
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    adapter = OpenAIAdapter(mock_client, model="gpt-4o")

    import asyncio

    reply, tool_calls = asyncio.run(adapter([{"role": "user", "content": "hi"}]))
    assert reply == "Hello from OpenAI!"
    assert tool_calls == []
