# Evaluators

Evaluators decide whether an agent's reply passes or fails a turn. All evaluators implement an async `evaluate(ctx: TurnContext) -> EvalResult` method.

## `ContainsEvaluator`

Checks that the reply contains expected substrings (case-insensitive).

```python
from pytest_llm_eval import ContainsEvaluator

# Pass if reply contains at least one of these
ContainsEvaluator(any_of=["confirmed", "booked"])

# Pass if reply contains ALL of these
ContainsEvaluator(all_of=["booking", "reference number"])

# Both checks at once
ContainsEvaluator(
    any_of=["confirmed", "booked"],
    all_of=["tomorrow"],
)
```

**Parameters:**

| Parameter | Type        | Description                                              |
|-----------|-------------|----------------------------------------------------------|
| `any_of`  | `list[str]` | Reply must contain at least one of these (case-insensitive) |
| `all_of`  | `list[str]` | Reply must contain every one of these (case-insensitive)  |

## `ToolCallEvaluator`

Validates that specific tools were (or were not) called during a turn.

```python
from pytest_llm_eval import ToolCallEvaluator

# Require a tool and forbid another
ToolCallEvaluator(
    must_include=["book_slot"],
    must_exclude=["cancel_slot"],
)

# Enforce call order
ToolCallEvaluator(
    must_include=["authenticate", "fetch_availability", "create_booking"],
    ordered=True,
)
```

**Parameters:**

| Parameter      | Type        | Description                                                        |
|----------------|-------------|--------------------------------------------------------------------|
| `must_include` | `list[str]` | Tool names that must appear in the turn's tool calls               |
| `must_exclude` | `list[str]` | Tool names that must NOT appear in the turn's tool calls           |
| `ordered`      | `bool`      | If `True`, `must_include` tools must appear in the specified order |

## `JudgeEvaluator`

Uses an LLM (via pydantic-ai) to evaluate the reply against a natural-language rubric. Good for open-ended quality checks that are hard to express as string patterns.

```python
from pytest_llm_eval import JudgeEvaluator

JudgeEvaluator(
    rubric=(
        "The reply must confirm the booking, include a reference number, "
        "mention the date and time, and have a friendly professional tone."
    ),
    model="openai:gpt-4o",      # optional — falls back to [tool.llm_eval] model
    retries=2,                   # retry API failures
    timeout=30.0,                # per-call timeout in seconds
)
```

**Parameters:**

| Parameter | Type           | Default       | Description                                                       |
|-----------|----------------|---------------|-------------------------------------------------------------------|
| `rubric`  | `str`          | required      | Natural-language description of what a passing reply looks like   |
| `model`   | `str \| None`  | `None`        | pydantic-ai model ID; falls back to `[tool.llm_eval] model`       |
| `retries` | `int`          | `2`           | Number of retries on API failure before returning a FAIL verdict  |
| `timeout` | `float`        | `30.0`        | Seconds before the judge call times out                           |

## Writing a custom evaluator

Implement the `Evaluator` protocol: an object with an async `evaluate` method.

```python
from pytest_llm_eval.models import TurnContext, EvalResult

class SentimentEvaluator:
    """Fail if the reply has negative sentiment."""

    def __init__(self, threshold: float = 0.5):
        self.threshold = threshold

    async def evaluate(self, ctx: TurnContext) -> EvalResult:
        # ctx.reply  — the agent's string reply
        # ctx.user   — the user message for this turn
        # ctx.tool_calls — list of tool names called
        # ctx.history    — OpenAI-format message history

        score = await compute_sentiment(ctx.reply)   # your own logic
        passed = score >= self.threshold
        return EvalResult(
            passed=passed,
            reasoning=f"Sentiment score {score:.2f} vs threshold {self.threshold:.2f}",
        )
```

Then use it like any built-in evaluator:

```python
from pytest_llm_eval import Turn, Expect

Turn(
    user="How was your experience?",
    expect=Expect(evaluators=[SentimentEvaluator(threshold=0.6)]),
)
```

The protocol requires only that `evaluate` is async and returns an `EvalResult`. There is no base class to inherit from.
