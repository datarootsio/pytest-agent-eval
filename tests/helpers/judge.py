"""Judge test doubles built on pydantic-ai's own test models.

``patch("pytest_agent_eval.evaluators.judge.Agent")`` mocks one of our own modules,
which CLAUDE.md forbids, and it also means the retry loop and structured-output
plumbing are never actually exercised. pydantic-ai ships ``TestModel`` and
``FunctionModel`` for exactly this, and the evaluators already accept a model object,
so no seam has to be invented.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic_ai.messages import ModelMessage, ModelResponse
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.test import TestModel


def verdict_model(*, passed: bool, reasoning: str) -> TestModel:
    """A judge model that always returns the given verdict.

    Goes through the real structured-output path, so a change to the judge's output
    type is caught here rather than silently mocked over.
    """
    return TestModel(custom_output_args={"passed": passed, "reasoning": reasoning})


@dataclass
class FailingJudge:
    """A judge model that raises, counting attempts.

    Exercises the real ``_run_judge`` retry loop instead of an ``AsyncMock``
    side-effect list, so the retry *count* is observed behaviour.
    """

    error: str = "API error"
    fail_times: int | None = None
    passed_after_recovery: bool = True
    attempts: int = 0
    _model: FunctionModel = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Build the FunctionModel that counts and raises."""
        self._model = FunctionModel(self._respond)

    def _respond(self, messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        self.attempts += 1
        if self.fail_times is None or self.attempts <= self.fail_times:
            raise RuntimeError(self.error)
        return _verdict_response(info, passed=self.passed_after_recovery, reasoning="recovered")

    @property
    def model(self) -> FunctionModel:
        """The pydantic-ai model to hand to an evaluator."""
        return self._model


@dataclass
class PromptCapturingJudge:
    """A judge model that records the prompt it received and returns a fixed verdict."""

    passed: bool = True
    reasoning: str = "ok"
    prompts: list[str] = field(default_factory=list)
    _model: FunctionModel = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Build the FunctionModel that records prompts."""
        self._model = FunctionModel(self._respond)

    def _respond(self, messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        self.prompts.append(
            "\n".join(
                str(getattr(part, "content", "")) for message in messages for part in getattr(message, "parts", [])
            )
        )
        return _verdict_response(info, passed=self.passed, reasoning=self.reasoning)

    @property
    def model(self) -> FunctionModel:
        """The pydantic-ai model to hand to an evaluator."""
        return self._model

    @property
    def last_prompt(self) -> str:
        """The most recent prompt the judge was sent."""
        return self.prompts[-1]


def _verdict_response(info: AgentInfo, *, passed: bool, reasoning: str) -> ModelResponse:
    """Build the structured-output tool call the judge agent expects."""
    from pydantic_ai.messages import ToolCallPart

    assert info.output_tools, "judge agent must declare a structured output tool"
    return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, {"passed": passed, "reasoning": reasoning})])
