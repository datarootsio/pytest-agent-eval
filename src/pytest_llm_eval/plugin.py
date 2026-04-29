"""pytest-llm-eval: hooks, markers, fixtures, and CLI options."""
from __future__ import annotations
import pytest
from pytest_llm_eval.config import load_config
from pytest_llm_eval.yaml_loader import pytest_collect_file  # noqa: F401


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("llm_eval", "LLM evaluation options")
    group.addoption(
        "--llm-eval-live",
        action="store_true",
        default=False,
        help="Enable live LLM evaluation tests (disabled by default to prevent accidental API charges).",
    )
    group.addoption(
        "--llm-eval-report",
        metavar="PATH",
        default=None,
        help="Write a markdown evaluation report to PATH after the test session.",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "llm_eval(threshold=None, runs=None): mark test as an LLM evaluation test. "
        "Skipped unless --llm-eval-live or EVAL_LIVE=1.",
    )
    from pytest_llm_eval.report import LLMEvalReportPlugin
    config.pluginmanager.register(LLMEvalReportPlugin(config), "llm_eval_report")


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    cfg = load_config(config)
    if cfg.live:
        return
    skip = pytest.mark.skip(reason="llm_eval: live mode disabled (use --llm-eval-live or EVAL_LIVE=1)")
    for item in items:
        if item.get_closest_marker("llm_eval") is not None:
            item.add_marker(skip)


@pytest.fixture
def llm_eval(request: pytest.FixtureRequest):
    """Fixture providing an EvalSession for the Python API.

    Returns:
        EvalSession configured with threshold and runs from the closest
        ``@pytest.mark.llm_eval`` marker, falling back to [tool.llm_eval] config.

    Example:
        ```python
        @pytest.mark.llm_eval(threshold=0.8, runs=3)
        async def test_booking(llm_eval):
            result = await llm_eval.run(agent=my_agent, turns=[...])
            result.assert_threshold()
        ```
    """
    from pytest_llm_eval.runner import EvalSession
    cfg = load_config(request.config)
    marker = request.node.get_closest_marker("llm_eval")
    threshold = marker.kwargs["threshold"] if (marker and "threshold" in marker.kwargs) else cfg.threshold
    runs = marker.kwargs["runs"] if (marker and "runs" in marker.kwargs) else cfg.runs
    return EvalSession(threshold=threshold, runs=runs, config_model=cfg.model, _item=request.node)
