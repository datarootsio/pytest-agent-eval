"""Adapter for smolagents agents (ToolCallingAgent, CodeAgent, ...)."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Protocol

from pytest_agent_eval.adapters._args import coerce_args
from pytest_agent_eval.models import AgentReply, History, ToolCall

if TYPE_CHECKING:
    from collections.abc import Sequence

_INTERNAL_TOOLS = frozenset({"python_interpreter", "final_answer"})


class _AgentMemory(Protocol):
    """A smolagents agent's memory: the list of steps it has taken."""

    @property
    def steps(self) -> Sequence[object]:
        """Every step taken so far, oldest first."""
        ...


class SmolagentsAgent(Protocol):
    """The slice of a smolagents agent the adapter uses: ``run`` plus ``memory.steps``.

    Steps are ``object``: only some of them carry ``tool_calls`` (a planning step does
    not), and the adapter's ``getattr`` default is what distinguishes the two.

    ``memory`` and ``steps`` are read-only ``@property`` members rather than plain
    attributes, and that is load-bearing: a Protocol attribute is *invariant*, so
    ``memory: _AgentMemory`` is a member no real ``MultiStepAgent`` can satisfy — declaring
    it a property makes it covariant, and the real class does. Getting this wrong is what
    made an earlier release reject the very SDK object this docstring names.
    """

    @property
    def memory(self) -> _AgentMemory:
        """The agent's accumulated memory."""
        ...

    def run(self, task: str, *, reset: bool) -> object:
        """Run one task, clearing the agent's memory first when ``reset``."""
        ...


class SmolagentsAdapter:
    """Wrap a smolagents agent to conform to the agent callable contract.

    Duck-typed: works with any object exposing ``.run(task, reset=...)`` and
    ``.memory.steps``. Smolagents's sync ``run`` is offloaded with
    ``asyncio.to_thread`` so the event loop stays responsive.

    Args:
        agent: A smolagents agent (e.g. ``ToolCallingAgent``, ``CodeAgent``).
        include_internal_tools: When ``True``, smolagents-internal pseudo-tools
            (``python_interpreter``, ``final_answer``) are included in the
            returned tool-call list. Defaults to ``False``.

    Example:
        ```python
        from smolagents import ToolCallingAgent, InferenceClientModel
        from pytest_agent_eval.adapters.smolagents import SmolagentsAdapter

        model = InferenceClientModel(model_id="meta-llama/Llama-3.3-70B-Instruct")
        agent = ToolCallingAgent(tools=[...], model=model)

        @pytest.fixture
        def llm_eval_agent():
            return SmolagentsAdapter(agent)
        ```
    """

    def __init__(self, agent: SmolagentsAgent, *, include_internal_tools: bool = False) -> None:
        """Store the smolagents agent and the internal-tool filter setting."""
        # The Protocol is on the parameter, so a type checker rejects a wrong object at the
        # call site. The guard is for callers without one: it names the extra to install,
        # which an assignability error does not.
        if not hasattr(agent, "run") or not hasattr(agent, "memory"):
            raise TypeError(
                f"SmolagentsAdapter expects a smolagents agent with .run() and .memory.steps, "
                f"got {type(agent).__name__}. Make sure the extra is installed: "
                "pip install 'pytest-agent-eval[smolagents]'"
            )
        self._agent = agent
        self._include_internal_tools = include_internal_tools

    async def __call__(self, history: History) -> AgentReply:
        """Run the agent against the latest user message and return (reply, tool_calls)."""
        user_msg = history[-1].content if history else ""
        reset = len(history) == 1
        prev = len(self._agent.memory.steps)
        result = await asyncio.to_thread(self._agent.run, user_msg, reset=reset)
        new_steps = self._agent.memory.steps[prev:] if not reset else self._agent.memory.steps
        calls = [
            ToolCall(tc.name, coerce_args(getattr(tc, "arguments", None)))
            for step in new_steps
            for tc in getattr(step, "tool_calls", None) or []
        ]
        if not self._include_internal_tools:
            calls = [c for c in calls if c not in _INTERNAL_TOOLS]
        return AgentReply(str(result), calls)
