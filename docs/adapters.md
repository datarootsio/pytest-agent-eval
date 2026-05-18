# Adapters

Adapters bridge your existing agent framework to the `pytest-agent-eval` callable contract: an async function that accepts a list of OpenAI-style message dicts and returns a `(reply: str, tool_calls: list[str])` tuple.

## `PydanticAIAdapter`

Wraps a pydantic-ai `Agent` instance.

```python
from pydantic_ai import Agent
from pytest_agent_eval.adapters.pydantic_ai import PydanticAIAdapter
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
from pytest_agent_eval.adapters.langchain import LangChainAdapter
import pytest

# my_langchain_graph is any LangChain Runnable
@pytest.fixture
def llm_eval_agent():
    return LangChainAdapter(my_langchain_graph)
```

Install the optional extra for LangChain support:

=== "pip"

    ```bash
    pip install "pytest-agent-eval[langchain]"
    ```

=== "uv"

    ```bash
    uv add "pytest-agent-eval[langchain]"
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
from pytest_agent_eval.adapters.openai import OpenAIAdapter
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

=== "pip"

    ```bash
    pip install "pytest-agent-eval[openai]"
    ```

=== "uv"

    ```bash
    uv add "pytest-agent-eval[openai]"
    ```

**Constructor:**

| Parameter       | Type             | Description                                               |
|-----------------|------------------|-----------------------------------------------------------|
| `client`        | `AsyncOpenAI`    | An `AsyncOpenAI` or `AsyncAzureOpenAI` instance           |
| `model`         | `str`            | Model name, e.g. `"gpt-4o"`                              |
| `system_prompt` | `str \| None`    | Optional system prompt prepended to every request         |

## `SmolagentsAdapter`

Wraps a [smolagents](https://github.com/huggingface/smolagents) agent: `ToolCallingAgent`, `CodeAgent`, or any duck-typed agent exposing `.run()` and `.memory.steps`.

```python
from smolagents import ToolCallingAgent, InferenceClientModel
from pytest_agent_eval.adapters.smolagents import SmolagentsAdapter
import pytest

model = InferenceClientModel(model_id="meta-llama/Llama-3.3-70B-Instruct")
agent = ToolCallingAgent(tools=[...], model=model)

@pytest.fixture
def llm_eval_agent():
    return SmolagentsAdapter(agent)
```

Install the optional extra for smolagents support:

=== "pip"

    ```bash
    pip install "pytest-agent-eval[smolagents]"
    ```

=== "uv"

    ```bash
    uv add "pytest-agent-eval[smolagents]"
    ```

The adapter offloads the sync `agent.run` to a worker thread with `asyncio.to_thread`. It detects the first turn of a transcript via `len(history) == 1` and passes `reset=True` so each transcript starts with fresh agent memory; subsequent turns pass `reset=False` to continue the conversation.

Tool-call names are collected from new entries in `agent.memory.steps`. Smolagents-internal pseudo-tools (`python_interpreter`, used by `CodeAgent`, and `final_answer`, the termination tool) are filtered by default. Pass `include_internal_tools=True` to see them.

!!! note "CodeAgent and tool-call assertions"
    `CodeAgent` runs tools by executing generated Python; smolagents records only the `python_interpreter` step, not the inner tool calls. If you need fine-grained tool-call assertions with `ToolCallEvaluator`, use `ToolCallingAgent`.

**Constructor:**

| Parameter                | Type   | Default | Description                                                                  |
|--------------------------|--------|---------|------------------------------------------------------------------------------|
| `agent`                  | `Any`  | required | A smolagents agent (`ToolCallingAgent`, `CodeAgent`, or duck-typed equivalent) |
| `include_internal_tools` | `bool` | `False`  | When `True`, return `python_interpreter` and `final_answer` in tool calls    |

## `LiveKitAdapter` (voice) {#livekit-voice}

Wraps a [LiveKit Agents](https://docs.livekit.io/agents) `AgentSession` so you can drive a real voice agent from a WAV file per turn. The adapter:

1. Reads the WAV path from each turn's `audio:` field (resolved relative to the YAML directory).
2. Builds a fresh `(AgentSession, Agent)` pair via the user-supplied factory.
3. Streams the WAV at real-time pace into `session.input.audio`.
4. Captures `function_tools_executed` events as tool calls and `conversation_item_added` events (filtered to `assistant` items) as the reply.
5. Returns `(reply, tool_calls)` to the same evaluator surface used by text adapters.

```python
import pytest
from livekit.agents.voice import Agent, AgentSession
from livekit.plugins import openai
from pytest_agent_eval.adapters.livekit import LiveKitAdapter

def make_session():
    session = AgentSession(llm=openai.realtime.RealtimeModel())
    agent = Agent(instructions="You are a booking assistant.", tools=[...])
    return session, agent

@pytest.fixture
def llm_eval_agent():
    return LiveKitAdapter(make_session)
```

YAML transcript with WAV references (paths resolve relative to the YAML file's directory):

```yaml
# tests/evals/booking_voice.yaml
id: booking_voice
turns:
  - user: "Book me a slot tomorrow at 10am."
    audio: booking_t1.wav
    expect:
      tool_calls_include: [create_booking]
      reply_contains_any: [confirmed, booked]
```

Install the optional extra:

=== "pip"

    ```bash
    pip install "pytest-agent-eval[livekit]"
    ```

=== "uv"

    ```bash
    uv add "pytest-agent-eval[livekit]"
    ```

The extra pulls `livekit-agents>=0.12`, `livekit-plugins-openai>=0.10`, and `openai>=1.0`.

### Generating audio fixtures

A bundled CLI synthesises WAVs from each turn's `user:` text via OpenAI Realtime (text-in, audio-out). Hash sidecars (`<wav>.hash` = `sha256(turn.user)`) skip re-synthesis when the transcript hasn't changed. Real recordings work just as well; the adapter doesn't care how the WAV was produced.

```bash
# Synthesise every YAML under [tool.agent_eval].yaml_dirs
python -m pytest_agent_eval.synthesize_audio

# Explicit paths (file or directory)
python -m pytest_agent_eval.synthesize_audio tests/evals/
python -m pytest_agent_eval.synthesize_audio tests/evals/booking_voice.yaml

# Re-synth everything regardless of cache
python -m pytest_agent_eval.synthesize_audio --force
```

The CLI requires `OPENAI_API_KEY` and writes a `.gitignore` next to every WAV (`*.wav`, `*.wav.hash`) so generated audio stays local. Commit YAML transcripts only.

**Constructor:**

| Parameter         | Type                                | Default | Description                                                                |
|-------------------|-------------------------------------|---------|----------------------------------------------------------------------------|
| `session_factory` | `Callable[[], (AgentSession, Agent)]` | required | Returns a fresh session + agent on every call (one per turn)             |
| `sample_rate`     | `int`                               | `24000` | WAV sample rate in Hz; must match the input file                          |
| `frame_ms`        | `int`                               | `20`    | Frame size in ms; default matches OpenAI Realtime's preferred chunk size  |
| `grace_period_s`  | `float`                             | `8.0`   | Seconds to wait after WAV exhaustion for trailing tool calls              |
| `timeout_s`       | `float`                             | `30.0`  | Maximum seconds to wait for WAV exhaustion before forcibly closing        |

## Writing a custom adapter

Any async callable that accepts `list[dict]` and returns `(str, list[str])` works directly. No base class needed:

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
