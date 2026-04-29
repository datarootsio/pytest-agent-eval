# Getting Started

This guide walks you through installing `pytest-llm-eval` and writing your first passing evaluation test.

## Installation

```bash
pip install pytest-llm-eval
```

For framework-specific adapters, install optional extras:

```bash
pip install pytest-llm-eval[langchain]   # LangChain support
pip install pytest-llm-eval[openai]      # OpenAI client support
```

## Configure pyproject.toml

Add a `[tool.llm_eval]` section to your `pyproject.toml`:

```toml
[tool.llm_eval]
model     = "openai:gpt-4o"
threshold = 0.8
runs      = 3
```

## Write your first test — Python API

Create `tests/test_my_agent.py`:

```python
import pytest
from pytest_llm_eval import Turn, Expect, ContainsEvaluator

async def my_agent(messages):
    """Your agent callable — receives OpenAI-style messages, returns a string reply."""
    # Replace with your actual agent
    return "Your booking is confirmed for tomorrow at 10am."

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

You must also provide an `agent` fixture named `llm_eval_agent` so the YAML loader knows what to call:

```python
# tests/conftest.py
import pytest

@pytest.fixture
def llm_eval_agent():
    async def my_agent(messages):
        return "Your booking is confirmed for tomorrow at 10am."
    return my_agent
```

## Run the tests

By default, eval tests are **skipped** in CI to avoid unexpected API calls. Enable them explicitly:

```bash
# One-shot flag
pytest --llm-eval-live

# Or via environment variable
EVAL_LIVE=1 pytest
```

A passing run shows the score alongside the test name:

```
tests/test_my_agent.py::test_booking_confirmation PASSED [score=1.00 threshold=0.80 runs=3/3]
```

Use `-vv` for full turn-by-turn details including evaluator reasoning.
