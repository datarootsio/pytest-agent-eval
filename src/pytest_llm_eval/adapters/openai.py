"""Adapter for the raw OpenAI async client."""
from __future__ import annotations
from typing import Any


class OpenAIAdapter:
    """Wrap an AsyncOpenAI client to conform to the agent callable contract.

    Args:
        client: An ``openai.AsyncOpenAI`` or ``openai.AsyncAzureOpenAI`` instance.
        model: Model name to use for completions (e.g. ``"gpt-4o"``).
        system_prompt: Optional system prompt prepended to every call.

    Example:
        ```python
        from openai import AsyncOpenAI
        from pytest_llm_eval.adapters.openai import OpenAIAdapter

        @pytest.fixture
        def llm_eval_agent():
            client = AsyncOpenAI()
            return OpenAIAdapter(client, model="gpt-4o")
        ```
    """

    def __init__(
        self,
        client: Any,
        model: str,
        system_prompt: str | None = None,
    ) -> None:
        self._client = client
        self._model = model
        self._system_prompt = system_prompt

    async def __call__(self, history: list[dict[str, Any]]) -> tuple[str, list[str]]:
        """Run a chat completion and normalise to (reply, tool_calls)."""
        messages: list[dict[str, Any]] = []
        if self._system_prompt:
            messages.append({"role": "system", "content": self._system_prompt})
        messages.extend(history)

        response = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
        )
        message = response.choices[0].message
        reply = message.content or ""
        tool_calls = [tc.function.name for tc in (message.tool_calls or [])]
        return reply, tool_calls
