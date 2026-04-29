# Getting Started

This guide walks you through installing `pytest-llm-eval` and writing your first passing evaluation test.

## Installation

=== "pip"

    ```bash
    pip install pytest-llm-eval
    ```

=== "uv"

    ```bash
    uv add pytest-llm-eval
    ```

For framework-specific adapters, install the matching optional extra:

=== "pip"

    ```bash
    pip install "pytest-llm-eval[langchain]"   # LangChain / LangGraph support
    pip install "pytest-llm-eval[openai]"      # OpenAI SDK support
    pip install "pytest-llm-eval[xdist]"       # parallel test execution
    ```

=== "uv"

    ```bash
    uv add "pytest-llm-eval[langchain]"
    uv add "pytest-llm-eval[openai]"
    uv add "pytest-llm-eval[xdist]"
    ```

## Configure pyproject.toml

Add a `[tool.llm_eval]` section to your `pyproject.toml`:

```toml
[tool.llm_eval]
model       = "openai:gpt-4o"   # default judge + agent-fallback model
threshold   = 0.8
runs        = 3
yaml_dirs   = ["tests/evals"]   # enables YAML auto-discovery
```

!!! tip "Use a separate judge model"
    Set `judge_model = "openai:gpt-4o"` independently from the agent-under-test model — you typically want a stronger model judging a cheaper agent.

## Write your first test — Python API

Create `tests/test_my_agent.py`:

```python
import pytest
from pytest_llm_eval import Turn, Expect, ContainsEvaluator

async def my_agent(messages):
    """Your agent callable — receives OpenAI-style messages, returns (reply, tool_calls)."""
    return "Your booking is confirmed for tomorrow at 10am.", []

@pytest.mark.llm_eval(threshold=0.8, runs=3)
async def test_booking_confirmation(llm_eval):
    result = await llm_eval.run(
        agent=my_agent,
        turns=[
            Turn(
                user="Book me a slot for tomorrow at 10am.",
                expect=Expect(
                    evaluators=[
                        ContainsEvaluator(any_of=["confirmed", "booked"]),
                        ContainsEvaluator(all_of=["tomorrow", "10"]),
                    ]
                ),
            )
        ],
    )
    result.assert_threshold()
```

## Write your first test — YAML style

!!! info "YAML auto-discovery"
    Any `*.yaml` file inside a directory listed in `yaml_dirs` becomes a pytest test automatically — no Python wrapper, no decorator. Drop a file, run `pytest`, see the result.

Create `tests/evals/booking.yaml`:

```yaml
id: booking_confirmation
threshold: 0.8
runs: 3
turns:
  - user: "Book me a slot for tomorrow at 10am."
    expect:
      reply_contains_any:
        - "confirmed"
        - "booked"
      reply_contains_all:
        - "tomorrow"
```

Then register the YAML directory in `pyproject.toml`:

```toml
[tool.llm_eval]
yaml_dirs = ["tests/evals"]
```

You must also provide an `llm_eval_agent` fixture so the loader knows what to call:

```python
# tests/conftest.py
import pytest

@pytest.fixture
def llm_eval_agent():
    async def my_agent(messages):
        return "Your booking is confirmed for tomorrow at 10am.", []
    return my_agent
```

## Run the tests

By default, eval tests are **skipped** in CI to avoid unexpected API calls. Enable them explicitly:

=== "Flag"

    ```bash
    pytest --llm-eval-live
    ```

=== "Environment"

    ```bash
    EVAL_LIVE=1 pytest
    ```

A passing run shows the score alongside the test name:

```
tests/test_my_agent.py::test_booking_confirmation PASSED [score=1.00 threshold=0.80 runs=3/3]
```

Use `-vv` for full turn-by-turn details including evaluator reasoning.

## Run in parallel

For large eval suites, install the `xdist` extra and pass `-n` to run tests across worker processes — results from every worker are aggregated into the report:

=== "pip"

    ```bash
    pip install "pytest-llm-eval[xdist]"
    pytest --llm-eval-live -n auto --llm-eval-report=eval.md
    ```

=== "uv"

    ```bash
    uv add "pytest-llm-eval[xdist]"
    uv run pytest --llm-eval-live -n auto --llm-eval-report=eval.md
    ```
