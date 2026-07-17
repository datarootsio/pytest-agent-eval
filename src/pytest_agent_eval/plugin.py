"""pytest-agent-eval: hooks, markers, fixtures, and CLI options."""

from __future__ import annotations

from typing import Any

import pytest

from pytest_agent_eval.config import load_config
from pytest_agent_eval.yaml_loader import pytest_collect_file  # noqa: F401


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register --agent-eval-live and --agent-eval-report CLI options."""
    group = parser.getgroup("agent_eval", "LLM evaluation options")
    group.addoption(
        "--agent-eval-live",
        action="store_true",
        default=False,
        help="Enable live LLM evaluation tests (disabled by default to prevent accidental API charges).",
    )
    group.addoption(
        "--agent-eval-report",
        metavar="PATH",
        default=None,
        help="Write a markdown evaluation report to PATH after the test session.",
    )


def pytest_configure(config: pytest.Config) -> None:
    """Register the agent_eval marker, validate group config, and add the report plugin."""
    config.addinivalue_line(
        "markers",
        "agent_eval(threshold=None, runs=None, tags=None): mark test as an LLM evaluation test. "
        "Skipped unless --agent-eval-live or EVAL_LIVE=1. tags feed [tool.agent_eval.groups] gates.",
    )
    try:
        cfg = load_config(config)
    except ValueError as exc:
        raise pytest.UsageError(str(exc)) from exc

    for group in cfg.groups:
        for marker_name in group.pytest_markers:
            config.addinivalue_line(
                "markers", f"{marker_name}: auto-registered by pytest-agent-eval group '{group.name}'"
            )

    from pytest_agent_eval.report import AgentEvalReportPlugin

    config.pluginmanager.register(AgentEvalReportPlugin(config), "llm_eval_report")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip agent_eval-marked items unless live mode is enabled."""
    cfg = load_config(config)
    if cfg.live:
        return
    skip = pytest.mark.skip(reason="agent_eval: live mode disabled (use --agent-eval-live or EVAL_LIVE=1)")
    skipped = 0
    for item in items:
        if item.get_closest_marker("agent_eval") is not None:
            item.add_marker(skip)
            skipped += 1
    config._agent_eval_live_skipped = skipped


def pytest_terminal_summary(terminalreporter: Any, exitstatus: int, config: pytest.Config) -> None:
    """Print a hint when eval tests were skipped because live mode is off."""
    skipped = getattr(config, "_agent_eval_live_skipped", 0)
    if skipped:
        terminalreporter.write_line(
            f"{skipped} eval test(s) skipped — live mode is off. Pass --agent-eval-live or set EVAL_LIVE=1.",
            yellow=True,
        )


@pytest.fixture
def agent_eval(request: pytest.FixtureRequest):
    """Fixture providing an EvalSession for the Python API.

    Returns:
        EvalSession configured with threshold and runs from the closest
        ``@pytest.mark.agent_eval`` marker, falling back to [tool.agent_eval] config.

    Example:
        ```python
        @pytest.mark.agent_eval(threshold=0.8, runs=3)
        async def test_booking(agent_eval):
            result = await agent_eval.run(agent=my_agent, turns=[...])
            result.assert_threshold()
        ```
    """
    from pytest_agent_eval.runner import EvalSession

    cfg = load_config(request.config)
    marker = request.node.get_closest_marker("agent_eval")
    threshold = marker.kwargs["threshold"] if (marker and "threshold" in marker.kwargs) else cfg.threshold
    runs = marker.kwargs["runs"] if (marker and "runs" in marker.kwargs) else cfg.runs
    return EvalSession(
        threshold=threshold, runs=runs, config_model=cfg.model, judge_model=cfg.judge_model, _item=request.node
    )
