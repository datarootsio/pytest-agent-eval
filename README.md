# pytest-agent-eval

[![PyPI version](https://img.shields.io/pypi/v/pytest-agent-eval.svg)](https://pypi.org/project/pytest-agent-eval/)
[![Python versions](https://img.shields.io/pypi/pyversions/pytest-agent-eval.svg)](https://pypi.org/project/pytest-agent-eval/)
[![License](https://img.shields.io/pypi/l/pytest-agent-eval.svg)](https://github.com/datarootsio/pytest-agent-eval/blob/main/LICENSE)
[![pytest plugin](https://img.shields.io/badge/pytest-plugin-0A9EDC?logo=pytest&logoColor=white)](https://docs.pytest.org/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://pre-commit.com/)

**LLM evaluation tests that actually mean something.** A pytest plugin for testing LLM agents with threshold-based pass/fail scoring, multi-turn transcripts, and LLM-as-judge rubrics — without breaking your CI bill.

## Highlights

- 🎯 **Threshold-based pass/fail** — run each test N times, pass when ≥ threshold% succeed
- 📝 **YAML or Python transcripts** — pick the authoring style your team prefers
- 🔍 **YAML auto-discovery** — drop `*.yaml` files in any configured directory and they become pytest tests automatically
- 🎙 **Voice agents (LiveKit)** — drive a real `AgentSession` with a WAV per turn; same evaluator surface as text agents
- 🛡 **CI-safe by default** — eval tests skip unless `--agent-eval-live` or `EVAL_LIVE=1`
- ⚡ **Parallel-ready** — `pytest -n auto` (via [`pytest-xdist`](https://pytest-xdist.readthedocs.io/)) just works
- 📄 **Markdown reports** — full per-run trace with `--agent-eval-report=eval.md`

## Installation

```bash
# pip
pip install pytest-agent-eval

# uv
uv add pytest-agent-eval
```

## Supported frameworks

`pytest-agent-eval` ships first-class adapters for the major Python agent frameworks. Each is an optional extra so you only install what you use.

| Framework | Extra | Adapter |
|---|---|---|
| [pydantic-ai](https://ai.pydantic.dev/) | _(default)_ | `pytest_agent_eval.adapters.pydantic_ai.PydanticAIAdapter` |
| [LangChain / LangGraph](https://python.langchain.com/) | `langchain` | `pytest_agent_eval.adapters.langchain.LangChainAdapter` |
| [OpenAI SDK](https://github.com/openai/openai-python) | `openai` | `pytest_agent_eval.adapters.openai.OpenAIAdapter` |
| [smolagents](https://github.com/huggingface/smolagents) | `smolagents` | `pytest_agent_eval.adapters.smolagents.SmolagentsAdapter` |
| [LiveKit (voice)](https://docs.livekit.io/agents) | `livekit` | `pytest_agent_eval.adapters.livekit.LiveKitAdapter` |

```bash
pip install "pytest-agent-eval[langchain]"
pip install "pytest-agent-eval[openai]"
pip install "pytest-agent-eval[smolagents]"
pip install "pytest-agent-eval[livekit]"
# or with uv:
uv add "pytest-agent-eval[langchain]"
uv add "pytest-agent-eval[openai]"
uv add "pytest-agent-eval[smolagents]"
uv add "pytest-agent-eval[livekit]"
```

Bringing your own framework? Any `async def agent(messages) -> (reply, tool_calls)` callable works directly — no base class needed.

## What you can test

`pytest-agent-eval` separates the *kinds of checks* you might want into composable evaluators:

- **Deterministic checks** — `ContainsEvaluator(any_of=["confirmed", "booked"], matches_all=[r"BK-\d+"])` for substring and regex assertions over the agent reply.
- **Tool-call assertions** — `ToolCallEvaluator(must_include=["create_booking"], ordered=True)` to verify that the agent called the right tools, in the right order.
- **Tool-argument assertions** — `ToolCallArgsEvaluator(tool="create_booking", args={"time": "10am"})` for deterministic subset/exact checks on call arguments, plus `ToolCallArgsJudgeEvaluator` for rubric-based judging of arguments.
- **LLM-as-judge** — `JudgeEvaluator(rubric="Reply must be friendly, include a date, and confirm the booking.")` for open-ended quality checks the agent under test should meet.

Mix and match per turn — every evaluator participates in the threshold score.

## Quick start

You can author evals two ways. **YAML is the recommended starting point** — it lets non-Python contributors (PMs, QA, domain experts) write tests, keeps eval data readable in code review, and turns each `.yaml` file into a pytest test automatically.

### 1 — Configure where YAMLs live

```toml
# pyproject.toml
[tool.agent_eval]
model     = "openai:gpt-4o"   # used by the LLM-as-judge
threshold = 0.8               # default pass fraction
runs      = 3                 # default reps per transcript
yaml_dirs = ["tests/evals"]
```

### 2 — Wire up your agent once

```python
# tests/conftest.py
import pytest
from pytest_agent_eval.adapters.pydantic_ai import PydanticAIAdapter
from my_app import build_agent

@pytest.fixture
def llm_eval_agent():
    return PydanticAIAdapter(build_agent())
```

### 3 — Write transcripts as YAML

```yaml
# tests/evals/booking_single_turn.yaml
id: booking_single_turn
threshold: 0.8
runs: 3

turns:
  - user: "Book me a slot tomorrow at 10am."
    expect:
      reply_contains_any: ["confirmed", "booked"]
      tool_calls_include: ["create_booking"]
      judge:
        rubric: "Reply must confirm the booking and include a reference number."
```

### 4 — Run it

```bash
pytest --agent-eval-live
```

```text
============================ test session starts =============================
plugins: agent-eval-0.1.0, asyncio-1.0.0
collected 2 items

tests/evals/booking_single_turn.yaml::booking_single_turn PASSED       [ 50%]
tests/evals/booking_multi_turn.yaml::booking_multi_turn PASSED         [100%]

============================== 2 passed in 14.03s ============================
```

By default eval tests are **skipped** outside of explicit live runs (so a missed `pytest .` doesn't burn API credits). Flip `--agent-eval-live` on, set `EVAL_LIVE=1`, or `live = true` in `[tool.agent_eval]` for local-only auto-on. See [Configuration](https://datarootsio.github.io/pytest-agent-eval/latest/configuration/) for the full precedence rules.

## Multi-turn conversations

Real agents fail on context, not single-shot replies. A model that nails turn 1 might forget the user's name by turn 3, or call the wrong tool once the user changes their mind. Multi-turn YAML transcripts test the **whole conversation arc**, with each turn asserting against the agent's state at that point:

```yaml
# tests/evals/booking_multi_turn.yaml
id: booking_multi_turn
threshold: 0.66          # tolerate 1/3 flaky runs
runs: 3
tags: [gate:booking, smoke]

turns:
  # Turn 1 — initial booking
  - user: "Book me a slot tomorrow at 10am."
    expect:
      reply_contains_any: ["confirmed", "booked"]
      tool_calls_include: ["create_booking"]

  # Turn 2 — agent must remember the booking from turn 1
  - user: "Actually, can you move it to 11am instead?"
    expect:
      tool_calls_include: ["update_booking"]
      tool_calls_exclude: ["create_booking"]   # must update, not double-book
      judge:
        rubric: "Confirms the new time AND references the original 10am booking."

  # Turn 3 — context propagates further
  - user: "Email me the confirmation."
    expect:
      tool_calls_include: ["send_email"]
      reply_contains_any: ["sent", "email"]
```

Each turn's full conversation history is built up as the test runs — your agent receives all prior `(user, assistant)` pairs as context, the same way it would in production. Failures point at the exact turn that broke, not just "the test failed."

## Voice agents (LiveKit)

The `[livekit]` extra adds a `LiveKitAdapter` that drives a real LiveKit `AgentSession` from a WAV per turn. Every turn declares an `audio:` path — the adapter streams it at real-time pace, captures `function_tools_executed` and `conversation_item_added` events, and returns `(reply, tool_calls)` to the same evaluators you already use for text agents:

```yaml
# tests/evals/booking_voice.yaml
id: booking_voice
turns:
  - user: "Book me a slot tomorrow at 10am."
    audio: booking_t1.wav            # resolved relative to this YAML's directory
    expect:
      tool_calls_include: [create_booking]
      reply_contains_any: [confirmed, booked]
```

```python
# tests/conftest.py
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

A bundled CLI generates the WAVs from each turn's `user:` text via OpenAI Realtime — hash-cached so unchanged transcripts skip re-synthesis, and idempotent enough for CI prebuilds:

```bash
python -m pytest_agent_eval.synthesize_audio                    # walks [tool.agent_eval].yaml_dirs
python -m pytest_agent_eval.synthesize_audio tests/evals/      # explicit dir
python -m pytest_agent_eval.synthesize_audio --force            # ignore cache
```

The CLI auto-writes a `.gitignore` next to every WAV (`*.wav`, `*.wav.hash`) so generated audio stays local — commit YAML transcripts only. Real recordings work too: drop a hand-recorded WAV at the same path and the adapter doesn't care how it got there.

See [Voice testing](docs/adapters.md#livekit-voice) for the full reference (sample rate, frame size, grace period, custom session factories).

## Sample report

Add `--agent-eval-report=eval.md` to get a human-readable trail of every run, every turn, and every evaluator's reasoning. Useful for CI artifacts and PR diffs:

```bash
pytest --agent-eval-live --agent-eval-report=eval.md
```

```markdown
# LLM Eval Report — 2026-04-30

## Summary

| Transcript            | Runs | Passed | Score | Threshold | Status  |
|-----------------------|------|--------|-------|-----------|---------|
| booking_single_turn   | 3    | 3      | 1.00  | 0.80      | ✅ PASS |
| booking_multi_turn    | 3    | 2      | 0.67  | 0.66      | ✅ PASS |

## Details

### booking_multi_turn
**Run 1** ✅
- Turn 1: PASS
- Turn 2: PASS
  - Judge: Reply confirmed move to 11am and acknowledged original 10am slot.
- Turn 3: PASS
**Run 2** ❌
- Turn 1: PASS
- Turn 2: FAIL
  - Tool calls expected to include 'update_booking', got ['create_booking']
- Turn 3: PASS
**Run 3** ✅
- ...
```

The two-out-of-three pass still clears the `0.66` threshold, so the suite passes — that's the point of running each transcript multiple times instead of treating LLM tests as binary.

## Python API

YAML covers most cases; drop into Python when you need parametrization, programmatic test generation, or per-test fixtures:

```python
import pytest
from pytest_agent_eval import Turn, Expect, ContainsEvaluator, ToolCallEvaluator, JudgeEvaluator

@pytest.mark.agent_eval(threshold=0.8, runs=3)
async def test_booking(agent_eval):
    result = await agent_eval.run(
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

See the [full documentation](https://datarootsio.github.io/pytest-agent-eval/latest/) (or [`/main/`](https://datarootsio.github.io/pytest-agent-eval/main/) for the in-development version) for the complete YAML reference, configuration options, parallel execution, and CI patterns. Contributions are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT — see [LICENSE](LICENSE).
