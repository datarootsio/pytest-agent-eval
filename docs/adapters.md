# Adapters

Adapters bridge your existing agent framework to the `pytest-llm-eval` callable contract: an async function that accepts a list of OpenAI-style message dicts and returns a `(reply: str, tool_calls: list[str])` tuple.

## `PydanticAIAdapter`

Wraps a pydantic-ai `Agent` instance.

```python
from pydantic_ai import Agent
from pytest_llm_eval.adapters.pydantic_ai import PydanticAIAdapter
import pytest

my_agent = Agent("openai:gpt-4o", system_prompt="You are a helpful booking assistant.")

@pytest.fixture
def llm_eval_agent():
    return PydanticAIAdapter(my_agent)
```

The adapter forwards the last message as the user prompt and the preceding messages as `message_history`. Tool names are extracted from `result.all_messages()`.

**Constructor:**

| Parameter | Type    | Description                             |
|-----------|---------|-----------------------------------------|
| `agent`   | `Agent` | A pydantic-ai `Agent` instance          |

## `LangChainAdapter`

Wraps a LangChain Runnable (compiled graph, chain, etc.).

```python
from pytest_llm_eval.adapters.langchain import LangChainAdapter
import pytest

# my_langchain_graph is any LangChain Runnable
@pytest.fixture
def llm_eval_agent():
    return LangChainAdapter(my_langchain_graph)
```

Install the optional extra for LangChain support:

```bash
pip install pytest-llm-eval[langchain]
```

The adapter calls `ainvoke({"messages": history})` and extracts `content` and `tool_calls` from the result. It handles both direct `AIMessage` returns and `{"messages": [...]}` dict returns from compiled graphs.

**Constructor:**

| Parameter  | Type       | Description                              |
|------------|------------|------------------------------------------|
| `runnable` | `Runnable` | A LangChain Runnable or compiled graph   |

## `OpenAIAdapter`

Wraps the raw `AsyncOpenAI` or `AsyncAzureOpenAI` client.

```python
from openai import AsyncOpenAI
from pytest_llm_eval.adapters.openai import OpenAIAdapter
import pytest

@pytest.fixture
def llm_eval_agent():
    client = AsyncOpenAI()   # reads OPENAI_API_KEY from environment
    return OpenAIAdapter(
        client,
        model="gpt-4o",
        system_prompt="You are a helpful booking assistant.",
    )
```

Install the optional extra for OpenAI support:

```bash
pip install pytest-llm-eval[openai]
```

**Constructor:**

| Parameter       | Type             | Description                                               |
|-----------------|------------------|-----------------------------------------------------------|
| `client`        | `AsyncOpenAI`    | An `AsyncOpenAI` or `AsyncAzureOpenAI` instance           |
| `model`         | `str`            | Model name, e.g. `"gpt-4o"`                              |
| `system_prompt` | `str \| None`    | Optional system prompt prepended to every request         |

## Writing a custom adapter

Any async callable that accepts `list[dict]` and returns `(str, list[str])` works directly — no base class needed:

```python
import pytest

async def my_custom_agent(messages: list[dict]) -> tuple[str, list[str]]:
    """
    messages: OpenAI-style [{"role": "user", "content": "..."}, ...]
    Returns: (reply_text, list_of_tool_names_called)
    """
    user_text = messages[-1]["content"]
    reply = await call_my_backend(user_text)
    return reply, []    # return empty list if no tool tracking

@pytest.fixture
def llm_eval_agent():
    return my_custom_agent
```

If your agent wraps a synchronous function, use `asyncio.to_thread`:

```python
import asyncio

async def my_sync_wrapper(messages):
    def _sync(text):
        return my_blocking_agent(text), []
    return await asyncio.to_thread(_sync, messages[-1]["content"])
```
