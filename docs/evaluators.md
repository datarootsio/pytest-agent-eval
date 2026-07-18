# Evaluators

Evaluators decide whether an agent's reply passes or fails a turn. All evaluators implement an async `evaluate(ctx: TurnContext) -> EvalResult` method.

## `ContainsEvaluator`

Checks that the reply contains expected substrings or matches regex patterns (case-insensitive by default).

```python
from pytest_agent_eval import ContainsEvaluator

# Pass if reply contains at least one of these
ContainsEvaluator(any_of=["confirmed", "booked"])

# Pass if reply contains ALL of these
ContainsEvaluator(all_of=["booking", "reference number"])

# Regex patterns (evaluated with re.search)
ContainsEvaluator(matches_any=[r"ref(erence)? number[:# ]*[A-Z]{2}-\d+"])
ContainsEvaluator(matches_all=[r"\d{1,2}(am|pm)", r"tomorrow"])

# Substring and regex checks compose freely
ContainsEvaluator(
    any_of=["confirmed", "booked"],
    matches_all=[r"BK-\d+"],
)

# Exact-case matching
ContainsEvaluator(all_of=["Booking"], case_sensitive=True)
```

Invalid regex patterns raise `ValueError` at construction time, so a typo fails the test suite immediately instead of silently failing every turn.

**Parameters:**

| Parameter        | Type        | Description                                                       |
|------------------|-------------|-------------------------------------------------------------------|
| `any_of`         | `list[str]` | Reply must contain at least one of these substrings               |
| `all_of`         | `list[str]` | Reply must contain every one of these substrings                  |
| `matches_any`    | `list[str]` | Reply must match at least one of these regex patterns (`re.search`) |
| `matches_all`    | `list[str]` | Reply must match every one of these regex patterns (`re.search`)  |
| `case_sensitive` | `bool`      | When `False` (default), all checks ignore case                    |

## `ToolCallEvaluator`

Validates that specific tools were (or were not) called during a turn.

```python
from pytest_agent_eval import ToolCallEvaluator

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

## `ToolCallArgsEvaluator`

Asserts the **arguments** a tool was called with. Requires an adapter (or custom agent) that captures arguments — all bundled adapters do; custom agents return `ToolCall(name, args)` instead of plain strings (see [Adapters](adapters.md#writing-a-custom-adapter)).

```python
from pytest_agent_eval import ToolCallArgsEvaluator

# Subset (default): expected top-level keys/values must appear; extra observed keys are fine
ToolCallArgsEvaluator(tool="book_slot", args={"time": "10am"})

# Exact: observed args must equal the expected dict exactly
ToolCallArgsEvaluator(tool="book_slot", args={"time": "10am", "date": "tomorrow"}, mode="exact")
```

Subset matching compares top-level keys only; a nested dict value is compared exactly (`{"opts": {"a": 1}}` does not subset-match `{"opts": {"a": 1, "b": 2}}`). Use `mode="exact"` when you want full equality, or assert the nested keys with a separate entry.

If the tool is called several times in a turn, the check passes when **any** call matches. Failure messages distinguish three cases: the tool was never called, the tool was called but no dict arguments were captured, and a genuine argument mismatch (which shows expected vs observed).

**Parameters:**

| Parameter | Type   | Default    | Description                                        |
|-----------|--------|------------|----------------------------------------------------|
| `tool`    | `str`  | required   | Name of the tool to check                          |
| `args`    | `dict` | required   | Expected arguments                                 |
| `mode`    | `str`  | `"subset"` | `"subset"` or `"exact"`                            |

## `ToolCallArgsJudgeEvaluator`

Uses an LLM to judge a tool's arguments against a natural-language rubric — for constraints that are awkward to express as exact values ("the time must be within business hours", "the query must mention the user's city").

```python
from pytest_agent_eval import ToolCallArgsJudgeEvaluator

ToolCallArgsJudgeEvaluator(
    tool="book_slot",
    rubric="The booking time must be within business hours (9am-5pm).",
)
```

The judge receives the tool name and the JSON arguments of every call to that tool in the turn, and passes if any call satisfies the rubric. Never-called and args-not-captured fail deterministically **before** any LLM call, so no judge tokens are spent on structural failures.

**Parameters:**

| Parameter | Type          | Default  | Description                                                  |
|-----------|---------------|----------|--------------------------------------------------------------|
| `tool`    | `str`         | required | Name of the tool whose arguments to judge                    |
| `rubric`  | `str`         | required | Natural-language rubric for acceptable arguments             |
| `model`   | `str \| None` | `None`   | pydantic-ai model ID; falls back to `[tool.agent_eval] model` |
| `retries` | `int`         | `2`      | Retries on API failure                                       |
| `timeout` | `float`       | `30.0`   | Per-call timeout in seconds                                  |

## `JudgeEvaluator`

Uses an LLM (via pydantic-ai) to evaluate the reply against a natural-language rubric. Good for open-ended quality checks that are hard to express as string patterns.

```python
from pytest_agent_eval import JudgeEvaluator

JudgeEvaluator(
    rubric=(
        "The reply must confirm the booking, include a reference number, "
        "mention the date and time, and have a friendly professional tone."
    ),
    model="openai:gpt-4o",      # optional; falls back to [tool.agent_eval] model
    retries=2,                   # retry API failures
    timeout=30.0,                # per-call timeout in seconds
)
```

**Parameters:**

| Parameter | Type           | Default       | Description                                                       |
|-----------|----------------|---------------|-------------------------------------------------------------------|
| `rubric`  | `str`          | required      | Natural-language description of what a passing reply looks like   |
| `model`   | `str \| None`  | `None`        | pydantic-ai model ID; falls back to `[tool.agent_eval] model`       |
| `retries` | `int`          | `2`           | Number of retries on API failure before returning a FAIL verdict  |
| `timeout` | `float`        | `30.0`        | Seconds before the judge call times out                           |

## Writing a custom evaluator

Implement the `Evaluator` protocol: an object with an async `evaluate` method.

```python
from pytest_agent_eval.models import TurnContext, EvalResult

class SentimentEvaluator:
    """Fail if the reply has negative sentiment."""

    def __init__(self, threshold: float = 0.5):
        self.threshold = threshold

    async def evaluate(self, ctx: TurnContext) -> EvalResult:
        # ctx.reply:      the agent's string reply
        # ctx.user:       the user message for this turn
        # ctx.tool_calls: list of tool names called
        # ctx.history:    OpenAI-format message history

        score = await compute_sentiment(ctx.reply)   # your own logic
        passed = score >= self.threshold
        return EvalResult(
            passed=passed,
            reasoning=f"Sentiment score {score:.2f} vs threshold {self.threshold:.2f}",
        )
```

Then use it like any built-in evaluator:

```python
from pytest_agent_eval import Turn, Expect

Turn(
    user="How was your experience?",
    expect=Expect(evaluators=[SentimentEvaluator(threshold=0.6)]),
)
```

The protocol requires only that `evaluate` is async and returns an `EvalResult`. There is no base class to inherit from.
