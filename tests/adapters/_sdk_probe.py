"""Type-level probe: every adapter must accept the real SDK class its docstring names.

Nothing in this module is ever called — ``test_sdk_types.py`` runs ``ty`` over it instead.
The bug it guards against is purely static, which is why a normal test cannot catch it: a
Protocol member declared as a mutable attribute is *invariant*, so no real SDK class
satisfies it, yet the adapter still imports and passes every fake-based test. That exact
regression shipped once and had to be hot-fixed. Spelling the members ``@property`` makes
them covariant; this file is what proves it stayed that way.

The adapters are constructed from a *parameter* annotated with the real SDK type rather
than from a freshly built object, so the check is assignability alone — no API keys, no
network, and no dependence on a constructor signature that the SDK may change.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pytest_agent_eval.adapters.langchain import LangChainAdapter
from pytest_agent_eval.adapters.livekit import LiveKitAdapter
from pytest_agent_eval.adapters.openai import OpenAIAdapter
from pytest_agent_eval.adapters.pydantic_ai import PydanticAIAdapter
from pytest_agent_eval.adapters.smolagents import SmolagentsAdapter

if TYPE_CHECKING:
    from langchain_core.runnables import RunnableLambda, RunnableSequence
    from livekit.agents.voice import Agent as LiveKitAgent
    from livekit.agents.voice import AgentSession
    from openai import AsyncAzureOpenAI, AsyncOpenAI
    from pydantic_ai import Agent as PydanticAgent
    from smolagents import CodeAgent, MultiStepAgent, ToolCallingAgent


def probe_openai(client: AsyncOpenAI) -> OpenAIAdapter:
    """A real AsyncOpenAI is what the docstring tells users to pass."""
    return OpenAIAdapter(client, model="gpt-4o")


def probe_azure_openai(client: AsyncAzureOpenAI) -> OpenAIAdapter:
    """The docstring names AsyncAzureOpenAI too, so it must also be assignable."""
    return OpenAIAdapter(client, model="gpt-4o")


def probe_langchain_lambda(runnable: RunnableLambda[dict[str, object], object]) -> LangChainAdapter:
    """The simplest real Runnable."""
    return LangChainAdapter(runnable)


def probe_langchain_sequence(chain: RunnableSequence[dict[str, object], object]) -> LangChainAdapter:
    """A composed chain, which is what `|` actually produces."""
    return LangChainAdapter(chain)


def probe_smolagents_base(agent: MultiStepAgent) -> SmolagentsAdapter:
    """The base class every smolagents agent derives from.

    This is the assignment that failed before ``memory`` became a ``@property``.
    """
    return SmolagentsAdapter(agent)


def probe_smolagents_tool_calling(agent: ToolCallingAgent) -> SmolagentsAdapter:
    """The concrete agent the docstring's example builds."""
    return SmolagentsAdapter(agent)


def probe_smolagents_code(agent: CodeAgent) -> SmolagentsAdapter:
    """The other concrete agent the docstring names."""
    return SmolagentsAdapter(agent)


def probe_pydantic_ai(agent: PydanticAgent[None, str]) -> PydanticAIAdapter:
    """A concrete pydantic-ai Agent, not the AbstractAgent supertype."""
    return PydanticAIAdapter(agent)


def probe_livekit(session: AgentSession[None], agent: LiveKitAgent) -> LiveKitAdapter:
    """A user's session_factory returns a real (AgentSession, Agent) pair."""
    return LiveKitAdapter(lambda: (session, agent))
