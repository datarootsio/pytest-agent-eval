"""Adapter for the raw OpenAI async client."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pytest_agent_eval.adapters._args import coerce_args
from pytest_agent_eval.models import AgentReply, History, Message, ToolCall

if TYPE_CHECKING:
    from openai import AsyncOpenAI
    from openai.types.chat import ChatCompletionMessageParam, ChatCompletionMessageToolCallUnion


def _as_param(message: Message) -> ChatCompletionMessageParam:
    """Convert one Message into the SDK's own per-role message param.

    A role dispatch rather than ``m.to_dict()``: the SDK types ``messages`` as a union of
    per-role TypedDicts, and a ``dict[str, str]`` is not assignable to any of them. Reading
    only ``role`` and ``content`` also means the plugin-internal ``audio`` key cannot leak
    into a request that would reject it.
    """
    if message.role == "system":
        return {"role": "system", "content": message.content}
    if message.role == "assistant":
        return {"role": "assistant", "content": message.content}
    return {"role": "user", "content": message.content}


def _tool_call(raw: ChatCompletionMessageToolCallUnion) -> ToolCall:
    """Normalise either kind of tool call the SDK can return.

    ``tool_calls`` is a discriminated union, and only the function member has
    ``.function`` — the Protocol this replaced asserted otherwise, so a model emitting a
    custom tool call raised AttributeError here. A custom call's ``input`` is free text, so
    ``coerce_args`` reports "not captured" unless it happens to be JSON.
    """
    if raw.type == "custom":
        return ToolCall(raw.custom.name, coerce_args(raw.custom.input))
    return ToolCall(raw.function.name, coerce_args(raw.function.arguments))


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
        client: AsyncOpenAI,
        model: str,
        system_prompt: str | None = None,
    ) -> None:
        """Store the OpenAI client, model name, and optional system prompt."""
        # The real SDK type, imported under TYPE_CHECKING, and the sole adapter that cannot
        # use a Protocol: `create` is overloaded (streaming vs not), which no hand-rolled
        # structural type can express. The guard stays for callers with no type checker —
        # it is what turns a missing extra into a message naming it.
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
        messages: list[ChatCompletionMessageParam] = []
        if self._system_prompt:
            messages.append({"role": "system", "content": self._system_prompt})
        messages.extend(_as_param(m) for m in history)

        response = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
        )
        message = response.choices[0].message
        reply = message.content or ""
        return AgentReply(reply, [_tool_call(tc) for tc in (message.tool_calls or [])])
