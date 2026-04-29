# pytest-llm-eval

[![PyPI version](https://img.shields.io/pypi/v/pytest-llm-eval.svg)](https://pypi.org/project/pytest-llm-eval/)
[![Python versions](https://img.shields.io/pypi/pyversions/pytest-llm-eval.svg)](https://pypi.org/project/pytest-llm-eval/)
[![License](https://img.shields.io/pypi/l/pytest-llm-eval.svg)](https://github.com/datarootsio/pytest-llm-eval/blob/main/LICENSE)
[![pytest plugin](https://img.shields.io/badge/pytest-plugin-0A9EDC?logo=pytest&logoColor=white)](https://docs.pytest.org/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://pre-commit.com/)

**LLM evaluation tests that actually mean something.**

`pytest-llm-eval` is a pytest plugin for testing LLM agents and applications with threshold-based pass/fail scoring, multi-turn YAML transcripts, and an LLM-as-judge rubric system — without breaking your CI bill.

## Highlights

- 🎯 **Threshold-based pass/fail** — run each test N times, pass when ≥ threshold% succeed
- 📝 **YAML or Python transcripts** — pick the authoring style your team prefers
- 🔍 **YAML auto-discovery** — drop `*.yaml` files in any configured directory and they become pytest tests automatically
- 🛡 **CI-safe by default** — eval tests skip unless `--llm-eval-live` or `EVAL_LIVE=1`
- ⚡ **Parallel-ready** — `pytest -n auto` (via [`pytest-xdist`](https://pytest-xdist.readthedocs.io/)) just works
- 📄 **Markdown reports** — full per-run trace with `--llm-eval-report=eval.md`

## Install

=== "pip"

    ```bash
    pip install pytest-llm-eval
    ```

=== "uv"

    ```bash
    uv add pytest-llm-eval
    ```

For framework-specific adapters, install one of the optional extras shown in the [Frameworks](#supported-frameworks) section.

## What you can test

!!! tip "Three layers of checks, freely composable"
    Each evaluator runs against every turn and contributes to the threshold score. Mix the strict ones with the judgmental ones — there is no priority.

=== "Deterministic"

    Substring / pattern assertions over the agent's reply. Cheap, fast, deterministic.

    ```python
    from pytest_llm_eval import ContainsEvaluator

    ContainsEvaluator(any_of=["confirmed", "booked"])
    ContainsEvaluator(all_of=["reference", "tomorrow"])
    ```

=== "Tool calling"

    Assert that the agent invoked the right tools — optionally in a specific order, with disallowed tools.

    ```python
    from pytest_llm_eval import ToolCallEvaluator

    ToolCallEvaluator(
        must_include=["authenticate", "fetch_availability", "create_booking"],
        must_exclude=["cancel_booking"],
        ordered=True,
    )
    ```

=== "LLM as judge"

    Open-ended quality checks. The judge (a separate model) returns a verdict + reasoning against your rubric.

    ```python
    from pytest_llm_eval import JudgeEvaluator

    JudgeEvaluator(
        rubric=(
            "The reply must confirm the booking, include a reference "
            "number, and have a friendly professional tone."
        ),
        model="openai:gpt-4o",   # optional override; falls back to [tool.llm_eval] judge_model
    )
    ```

## Supported frameworks

`pytest-llm-eval` ships first-class adapters for the major Python agent frameworks. Each is an optional extra so you only install what you use.

=== "pydantic-ai"

    No extra needed — pydantic-ai support ships with the base install.

    === "pip"

        ```bash
        pip install pytest-llm-eval
        ```

    === "uv"

        ```bash
        uv add pytest-llm-eval
        ```

    ```python
    from pydantic_ai import Agent
    from pytest_llm_eval.adapters.pydantic_ai import PydanticAIAdapter

    my_agent = Agent("openai:gpt-4o", system_prompt="You are a helpful assistant.")

    @pytest.fixture
    def llm_eval_agent():
        return PydanticAIAdapter(my_agent)
    ```

=== "LangChain / LangGraph"

    === "pip"

        ```bash
        pip install "pytest-llm-eval[langchain]"
        ```

    === "uv"

        ```bash
        uv add "pytest-llm-eval[langchain]"
        ```

    ```python
    from pytest_llm_eval.adapters.langchain import LangChainAdapter

    @pytest.fixture
    def llm_eval_agent():
        return LangChainAdapter(my_compiled_graph)
    ```

=== "OpenAI SDK"

    === "pip"

        ```bash
        pip install "pytest-llm-eval[openai]"
        ```

    === "uv"

        ```bash
        uv add "pytest-llm-eval[openai]"
        ```

    ```python
    from openai import AsyncOpenAI
    from pytest_llm_eval.adapters.openai import OpenAIAdapter

    @pytest.fixture
    def llm_eval_agent():
        return OpenAIAdapter(AsyncOpenAI(), model="gpt-4o")
    ```

=== "Smolagents"

    === "pip"

        ```bash
        pip install "pytest-llm-eval[smolagents]"
        ```

    === "uv"

        ```bash
        uv add "pytest-llm-eval[smolagents]"
        ```

    ```python
    from smolagents import ToolCallingAgent, InferenceClientModel
    from pytest_llm_eval.adapters.smolagents import SmolagentsAdapter

    agent = ToolCallingAgent(tools=[...], model=InferenceClientModel(model_id="..."))

    @pytest.fixture
    def llm_eval_agent():
        return SmolagentsAdapter(agent)
    ```

=== "Custom"

    Any `async def agent(messages) -> tuple[reply: str, tool_calls: list[str]]` callable works as-is — no base class, no inheritance.

    ```python
    @pytest.fixture
    def llm_eval_agent():
        async def agent(messages):
            reply = await call_my_backend(messages[-1]["content"])
            return reply, []
        return agent
    ```

## YAML auto-discovery

!!! info "Zero-boilerplate evals"
    Point `pytest-llm-eval` at any directory of `*.yaml` files and every transcript becomes a pytest test — no Python wrapper required. Add files, run `pytest`, see results.

```toml
# pyproject.toml
[tool.llm_eval]
yaml_dirs = ["tests/evals"]
```

```yaml
# tests/evals/booking.yaml
id: booking_confirmation
threshold: 0.8
runs: 3
turns:
  - user: "Book me a slot tomorrow at 10am"
    expect:
      reply_contains_any: ["confirmed", "booked"]
      tool_calls_include: ["create_booking"]
      judge:
        rubric: "Reply must include a reference number and be polite."
```

Provide one shared `llm_eval_agent` fixture (in `conftest.py`) and the loader handles the rest. See the [YAML API reference](yaml-api.md) for every field.

## Quick start (Python API)

```python
import pytest
from pytest_llm_eval import Turn, Expect, ContainsEvaluator, ToolCallEvaluator, JudgeEvaluator

@pytest.mark.llm_eval(threshold=0.8, runs=3)
async def test_booking(llm_eval):
    result = await llm_eval.run(
        agent=my_agent,
        turns=[
            Turn(
                user="Book me a slot tomorrow at 10am",
                expect=Expect(evaluators=[
                    ContainsEvaluator(any_of=["confirmed", "booked"]),
                    ToolCallEvaluator(must_include=["create_booking"]),
                    JudgeEvaluator(rubric="Reply must include a reference number."),
                ]),
            )
        ],
    )
    result.assert_threshold()
```

```bash
pytest --llm-eval-live
```

See [Getting Started](getting-started.md) for a full walkthrough.
