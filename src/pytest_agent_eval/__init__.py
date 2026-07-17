"""pytest-agent-eval: LLM evaluation plugin for pytest."""

from importlib.metadata import version as _pkg_version

from pytest_agent_eval.evaluators import (
    ContainsEvaluator,
    EvalResult,
    Evaluator,
    JudgeEvaluator,
    ToolCallEvaluator,
)
from pytest_agent_eval.models import Expect, JudgeConfig, ToolCall, Transcript, Turn

__version__ = _pkg_version("pytest-agent-eval")

__all__ = [
    "Turn",
    "Expect",
    "Transcript",
    "JudgeConfig",
    "ToolCall",
    "Evaluator",
    "EvalResult",
    "ContainsEvaluator",
    "ToolCallEvaluator",
    "JudgeEvaluator",
    "__version__",
]
