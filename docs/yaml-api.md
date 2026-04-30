# YAML API

YAML transcripts let you define evaluation tests without writing Python. They are loaded automatically from any directory listed in `yaml_dirs`.

## Directory setup

```toml
# pyproject.toml
[tool.agent_eval]
yaml_dirs = ["tests/evals"]
```

Any `*.yaml` file inside `tests/evals/` (searched recursively) becomes a test.

## Full annotated transcript

```yaml
# tests/evals/booking.yaml

# Unique ID — used as the pytest test name
id: booking_confirmation

# Fraction of runs that must pass (0.0 – 1.0)
threshold: 0.8

# Number of times to run the full transcript
runs: 3

# Optional tags for quality-gate filtering
tags:
  - gate:booking
  - smoke

turns:
  - user: "Book me a table for 2 tomorrow at 10am."

    expect:
      # Reply must contain at least one of these strings (case-insensitive)
      reply_contains_any:
        - "confirmed"
        - "booked"

      # Reply must contain ALL of these strings (case-insensitive)
      reply_contains_all:
        - "tomorrow"
        - "10"

      # Tool names that must appear in this turn's tool calls
      tool_calls_include:
        - create_booking

      # Tool names that must NOT appear in this turn's tool calls
      tool_calls_exclude:
        - cancel_booking

      # LLM-as-judge rubric (requires a model in [tool.agent_eval])
      judge:
        rubric: >
          The reply must confirm a booking with a date, time, and
          reference number. The tone should be friendly and professional.
        model: "openai:gpt-4o"   # optional — overrides [tool.agent_eval] model

  - user: "Can you email me the confirmation?"
    expect:
      reply_contains_any:
        - "email"
        - "sent"
```

## Field reference

### Top-level fields

| Field       | Type         | Required | Default                      | Description                                   |
|-------------|--------------|----------|------------------------------|-----------------------------------------------|
| `id`        | `str`        | yes      | —                            | Unique test identifier, used as the test name |
| `threshold` | `float`      | no       | `[tool.agent_eval]` threshold  | Pass fraction required                        |
| `runs`      | `int`        | no       | `[tool.agent_eval]` runs       | Number of executions                          |
| `tags`      | `list[str]`  | no       | `[]`                         | Quality-gate tags for filtering               |
| `turns`     | `list[Turn]` | yes      | —                            | Ordered list of turns                         |

### `turns[].user`

The user message string for this turn. Required for every turn.

### `turns[].expect`

All `expect` fields are optional. Omit `expect` entirely for turns where you only care about the agent not crashing.

| Field                | Type          | Description                                          |
|----------------------|---------------|------------------------------------------------------|
| `reply_contains_any` | `list[str]`   | At least one string must appear in the reply         |
| `reply_contains_all` | `list[str]`   | All strings must appear in the reply                 |
| `tool_calls_include` | `list[str]`   | These tool names must be present in the turn's calls |
| `tool_calls_exclude` | `list[str]`   | These tool names must be absent from the turn's calls|
| `judge`              | `JudgeConfig` | LLM-as-judge rubric evaluation                       |

### `turns[].expect.judge`

| Field    | Type          | Description                                                |
|----------|---------------|------------------------------------------------------------|
| `rubric` | `str`         | Natural-language rubric sent to the judge model            |
| `model`  | `str \| null` | pydantic-ai model ID override; falls back to global config |

## Agent fixture

YAML-loaded tests require a pytest fixture named `llm_eval_agent` that returns your agent callable:

```python
# tests/conftest.py
import pytest

@pytest.fixture
def llm_eval_agent():
    async def my_agent(messages):
        # messages is a list of OpenAI-style {"role": ..., "content": ...} dicts
        return "Booking confirmed! Reference BK-1234."
    return my_agent
```

The fixture is resolved at collection time, so you can parametrize it or switch agents per test directory.
