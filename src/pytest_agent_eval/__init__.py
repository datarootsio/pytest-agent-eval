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
from pytest_agent_eval.models import (
    AgentReply,
    Expect,
    JudgeConfig,
    ToolCall,
    ToolCallArgsConfig,
    Transcript,
    Turn,
)
from pytest_agent_eval.yaml_loader import TranscriptError

__version__ = _pkg_version("pytest-agent-eval")

__all__ = [
    "AgentReply",
    "ContainsEvaluator",
    "EvalResult",
    "Evaluator",
    "Expect",
    "JudgeConfig",
    "JudgeEvaluator",
    "ToolCall",
    "ToolCallArgsConfig",
    "ToolCallArgsEvaluator",
    "ToolCallArgsJudgeEvaluator",
    "ToolCallEvaluator",
    "Transcript",
    "TranscriptError",
    "Turn",
    "__version__",
]
