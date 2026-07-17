# Python API

The Python API lets you write LLM evaluation tests as ordinary async pytest functions.

## The `@pytest.mark.agent_eval` marker

Decorate any async test function to mark it as an LLM evaluation:

```python
import pytest

@pytest.mark.agent_eval(threshold=0.8, runs=3)
async def test_my_agent(agent_eval):
    ...
```

**Parameters:**

| Parameter   | Type    | Default                   | Description                                 |
|-------------|---------|---------------------------|---------------------------------------------|
| `threshold` | `float` | from `[tool.agent_eval]`    | Fraction of runs that must pass (0.0–1.0)   |
| `runs`      | `int`   | from `[tool.agent_eval]`    | Number of times to execute the transcript   |

Without `--agent-eval-live` or `EVAL_LIVE=1`, marked tests are automatically skipped.

## The `agent_eval` fixture

The `agent_eval` fixture is injected by the plugin. Call `.run()` to execute your transcript:

```python
result = await agent_eval.run(agent=my_agent, turns=[...])
```

**`agent_eval.run()` parameters:**

| Parameter   | Type            | Description                                            |
|-------------|-----------------|--------------------------------------------------------|
| `agent`     | `Callable`      | Async callable: `(messages) -> (reply, tool_calls)`    |
| `turns`     | `list[Turn]`    | Ordered list of turns to execute                       |

Threshold and run count come from the `@pytest.mark.agent_eval(threshold=..., runs=...)` marker, falling back to `[tool.agent_eval]` config.

Returns a `TranscriptResult`.

## `Turn`

```python
from pytest_agent_eval import Turn, Expect

turn = Turn(
    user="Book me a slot for tomorrow.",
    expect=Expect(
        evaluators=[ContainsEvaluator(any_of=["confirmed", "booked"])],
        tool_calls_include=["create_booking"],
    ),
)
```

| Field    | Type     | Default        | Description                                |
|----------|----------|----------------|--------------------------------------------|
| `user`   | `str`    | required       | The user message sent to the agent         |
| `expect` | `Expect` | `Expect()`     | Expectations checked against the reply     |

## `Expect`

```python
from pytest_agent_eval import Expect

expect = Expect(
    evaluators=[...],               # programmatic evaluators
    reply_contains_any=["confirmed", "booked"],
    reply_contains_all=["booking", "reference"],
    tool_calls_include=["create_booking"],
    tool_calls_exclude=["delete_booking"],
)
```

| Field                | Type              | Description                                          |
|----------------------|-------------------|------------------------------------------------------|
| `evaluators`         | `list[Evaluator]` | Custom evaluator instances                           |
| `reply_contains_any` | `list[str]`       | Reply must contain at least one string               |
| `reply_contains_all` | `list[str]`       | Reply must contain all strings                       |
| `tool_calls_include` | `list[str]`       | These tool names must appear in the turn's calls     |
| `tool_calls_exclude` | `list[str]`       | These tool names must NOT appear in the turn's calls |
| `judge`              | `JudgeConfig`     | LLM-as-judge rubric (see Evaluators)                 |

## Evaluators

### `ContainsEvaluator`

```python
from pytest_agent_eval import ContainsEvaluator

ContainsEvaluator(any_of=["confirmed", "booked"])
ContainsEvaluator(all_of=["booking", "reference number"])
```

### `ToolCallEvaluator`

```python
from pytest_agent_eval import ToolCallEvaluator

ToolCallEvaluator(must_include=["create_booking"], must_exclude=["cancel_booking"])
```

### `JudgeEvaluator`

```python
from pytest_agent_eval import JudgeEvaluator

JudgeEvaluator(
    rubric="The reply must confirm a booking with a date and reference number.",
    model="openai:gpt-4o",   # optional; falls back to [tool.agent_eval] model
)
```

## `TranscriptResult` and `assert_threshold()`

```python
result = await agent_eval.run(agent=my_agent, turns=[...])

# Manual inspection
print(result.score)      # e.g. 0.67
print(result.passed)     # True / False
print(result.threshold)  # e.g. 0.8
print(result.runs)       # list of RunResult

# Raise AssertionError if score < threshold
result.assert_threshold()
```

## Full annotated example

```python
import pytest
from pytest_agent_eval import (
    Turn, Expect,
    ContainsEvaluator, ToolCallEvaluator, JudgeEvaluator,
)

async def booking_agent(messages):
    # Your real agent implementation here — return (reply, tool_calls)
    return "Booking confirmed! Reference: BK-1234 for tomorrow at 10am.", ["create_booking"]

@pytest.mark.agent_eval(threshold=0.8, runs=3)
async def test_full_booking_flow(agent_eval):
    result = await agent_eval.run(
        agent=booking_agent,
        turns=[
            Turn(
                user="I need to book a table for 2 tomorrow at 10am.",
                expect=Expect(
                    evaluators=[
                        ContainsEvaluator(any_of=["confirmed", "booked"]),
                        ToolCallEvaluator(must_include=["create_booking"]),
                        JudgeEvaluator(
                            rubric=(
                                "The reply must confirm the booking and include "
                                "a reference number and time."
                            )
                        ),
                    ]
                ),
            ),
            Turn(
                user="Can you send me a confirmation email?",
                expect=Expect(
                    reply_contains_any=["email", "sent", "confirmation"],
                ),
            ),
        ],
    )
    result.assert_threshold()
```
