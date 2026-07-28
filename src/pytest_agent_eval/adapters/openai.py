"""Adapter for the raw OpenAI async client."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from pytest_agent_eval.adapters._args import coerce_args
from pytest_agent_eval.models import AgentReply, History, ToolCall

if TYPE_CHECKING:
    from collections.abc import Sequence


class _Function(Protocol):
    """The function payload of one OpenAI tool call."""

    name: str
    arguments: str


class _ToolCall(Protocol):
    """One tool call on a chat-completion message."""

    function: _Function


class _CompletionMessage(Protocol):
    """The assistant message the adapter reads off a completion choice."""

    content: str | None
    tool_calls: Sequence[_ToolCall] | None


class _Choice(Protocol):
    """One chat-completion choice."""

    message: _CompletionMessage


class _ChatCompletion(Protocol):
    """A chat-completion response."""

    choices: Sequence[_Choice]


class _Completions(Protocol):
    """The ``chat.completions`` namespace."""

    async def create(self, *, model: str, messages: Sequence[dict[str, str]]) -> _ChatCompletion:
        """Request one chat completion."""
        ...


class _Chat(Protocol):
    """The ``chat`` namespace, which is also the attribute the constructor guards on."""

    completions: _Completions


class OpenAIClient(Protocol):
    """The slice of ``AsyncOpenAI`` the adapter uses: one chat-completions call."""

    chat: _Chat


class OpenAIAdapter:
    """Wrap an AsyncOpenAI client to conform to the agent callable contract.

    Args:
        client: An ``openai.AsyncOpenAI`` or ``openai.AsyncAzureOpenAI`` instance.
        model: Model name to use for completions (e.g. ``"gpt-4o"``).
        system_prompt: Optional system prompt prepended to every call.

    Example:
        ```python
        from openai import AsyncOpenAI
        from pytest_agent_eval.adapters.openai import OpenAIAdapter

        @pytest.fixture
        def llm_eval_agent():
            client = AsyncOpenAI()
            return OpenAIAdapter(client, model="gpt-4o")
        ```
    """

    def __init__(
        self,
        client: OpenAIClient,
        model: str,
        system_prompt: str | None = None,
    ) -> None:
        """Store the OpenAI client, model name, and optional system prompt."""
        if not hasattr(client, "chat"):
            raise TypeError(
                f"OpenAIAdapter expects an AsyncOpenAI-compatible client with .chat.completions, "
                f"got {type(client).__name__}. Make sure the extra is installed: "
                "pip install 'pytest-agent-eval[openai]'"
            )
        self._client = client
        self._model = model
        self._system_prompt = system_prompt

    async def __call__(self, history: History) -> AgentReply:
        """Run a chat completion and normalise to (reply, tool_calls)."""
        messages: list[dict[str, str]] = []
        if self._system_prompt:
            messages.append({"role": "system", "content": self._system_prompt})
        # to_dict() drops the plugin-internal audio key: the API rejects unknown
        # message keys, and runner.py sets one on every voice turn.
        messages.extend(m.to_dict() for m in history)

        response = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
        )
        message = response.choices[0].message
        reply = message.content or ""
        tool_calls = [
            ToolCall(tc.function.name, coerce_args(tc.function.arguments)) for tc in (message.tool_calls or [])
        ]
        return AgentReply(reply, tool_calls)
