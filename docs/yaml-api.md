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

# Unique ID, used as the pytest test name
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
        model: "openai:gpt-4o"   # optional; overrides [tool.agent_eval] model

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
| `id`        | `str`        | yes      | n/a                          | Unique test identifier, used as the test name |
| `threshold` | `float`      | no       | `[tool.agent_eval]` threshold  | Pass fraction required                        |
| `runs`      | `int`        | no       | `[tool.agent_eval]` runs       | Number of executions                          |
| `tags`      | `list[str]`  | no       | `[]`                         | Quality-gate tags for filtering               |
| `turns`     | `list[Turn]` | yes      | n/a                          | Ordered list of turns                         |

### `turns[].user`

The user message string for this turn. Required for every turn. Also acts as the transcript when an `audio:` fixture is generated for this turn.

### `turns[].audio`

Optional path to a WAV file used by voice adapters (e.g. [`LiveKitAdapter`](adapters.md#livekit-voice)). Resolved relative to the YAML file's directory unless absolute. Text adapters ignore this field; turns can mix audio and non-audio freely.

```yaml
turns:
  - user: "Book me a slot tomorrow at 10am."
    audio: booking_t1.wav        # → tests/evals/booking_t1.wav
    expect:
      tool_calls_include: [create_booking]
```

Generate the WAV from `user:` text via:

```bash
python -m pytest_agent_eval.synthesize_audio
```

The CLI hashes `turn.user` into a `<wav>.hash` sidecar and only re-synthesises when the transcript changes. See the [LiveKit adapter docs](adapters.md#livekit-voice) for the full pipeline.

### `turns[].expect`

All `expect` fields are optional. Omit `expect` entirely for turns where you only care about the agent not crashing.

| Field                | Type          | Description                                          |
|----------------------|---------------|------------------------------------------------------|
| `reply_contains_any` | `list[str]`   | At least one string must appear in the reply         |
| `reply_contains_all` | `list[str]`   | All strings must appear in the reply                 |
| `reply_matches_any`  | `list[str]`   | At least one regex pattern must match the reply      |
| `reply_matches_all`  | `list[str]`   | All regex patterns must match the reply              |
| `tool_calls_include` | `list[str]`   | These tool names must be present in the turn's calls |
| `tool_calls_exclude` | `list[str]`   | These tool names must be absent from the turn's calls|
| `judge`              | `JudgeConfig` | LLM-as-judge rubric evaluation                       |

String and regex checks are case-insensitive. Regex patterns use Python `re.search` semantics — quote them in YAML so `\d` and friends survive parsing:

```yaml
expect:
  reply_matches_any:
    - "BK-\\d+"
    - "ref(erence)? number"
```

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
        # Return (reply, tool_calls): the reply string plus the tool names called.
        return "Booking confirmed! Reference BK-1234.", ["create_booking"]
    return my_agent
```

The fixture is resolved at collection time, so you can parametrize it or switch agents per test directory.
