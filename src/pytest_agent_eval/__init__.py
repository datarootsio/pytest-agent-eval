"""pytest-agent-eval: LLM evaluation plugin for pytest."""

from importlib.metadata import version as _pkg_version

from pytest_agent_eval.evaluators import (
    ContainsEvaluator,
    EvalResult,
    Evaluator,
    JudgeEvaluator,
    ToolCallArgsEvaluator,
    ToolCallArgsJudgeEvaluator,
    ToolCallEvaluator,
)
from pytest_agent_eval.models import Expect, JudgeConfig, ToolCall, ToolCallArgsConfig, Transcript, Turn

__version__ = _pkg_version("pytest-agent-eval")

__all__ = [
    "Turn",
    "Expect",
    "Transcript",
    "JudgeConfig",
    "ToolCall",
    "ToolCallArgsConfig",
    "Evaluator",
    "EvalResult",
    "ContainsEvaluator",
    "ToolCallEvaluator",
    "ToolCallArgsEvaluator",
    "ToolCallArgsJudgeEvaluator",
    "JudgeEvaluator",
    "__version__",
]
