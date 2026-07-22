# Examples

The repository ships eight small, self-contained projects under [`examples/`](https://github.com/datarootsio/pytest-agent-eval/tree/main/examples) — one per feature. Each is a known-good starting point to copy from: CI exercises every one of them (see [`tests/test_examples.py`](https://github.com/datarootsio/pytest-agent-eval/blob/main/tests/test_examples.py)), so they never drift from the current release.

Every example except `voice-livekit` uses a deterministic mock agent, so it runs offline with no API key. Swap the `llm_eval_agent` fixture for a real [adapter](adapters.md) to point any of them at your own agent.

## Running an example

```bash
cd examples/single-turn
pip install pytest-agent-eval   # or: uv add pytest-agent-eval
pytest --agent-eval-live
```

!!! note "Two CI caveats"
    - **Judge rubrics are stubbed in CI.** Examples that use an LLM-as-judge (`multi-turn-judge`, `tool-call-args`) need an API key to run the real judge standalone.
    - **`voice-livekit` is collect-only in CI.** It needs live credentials and synthesized audio, so CI only verifies that it collects.

The sections below follow the same pedagogical order as the [examples README](https://github.com/datarootsio/pytest-agent-eval/blob/main/examples/README.md): start at the top and each one adds a single concept.

## single-turn

The minimal setup: one YAML transcript plus one `llm_eval_agent` fixture. Reach for this shape first — a single user turn with deterministic substring and tool-call checks is enough for most smoke tests, and it needs no Python test file at all.

=== "evals/booking.yaml"

    ```yaml
    id: booking_single_turn
    threshold: 1.0
    runs: 1
    turns:
      - user: "Book me a table for two tomorrow at 10am."
        expect:
          reply_contains_any: [confirmed, booked]
          tool_calls_include: [create_booking]
    ```

=== "conftest.py"

    ```python
    import pytest


    @pytest.fixture
    def llm_eval_agent():
        # Deterministic mock agent; replace with a framework adapter to test yours.
        async def agent(history):
            return "Booking confirmed! Reference BK-1234.", ["create_booking"]

        return agent
    ```

[Runnable project ↗](https://github.com/datarootsio/pytest-agent-eval/tree/main/examples/single-turn)

## multi-turn-judge

A multi-turn conversation where the second turn is graded by an LLM-as-judge rubric. Reach for this when correctness depends on context carried across turns — here the assistant must reschedule the *existing* booking without asking the user to repeat themselves, which no substring check can verify.

=== "evals/reschedule.yaml"

    ```yaml
    id: booking_reschedule
    threshold: 1.0
    runs: 1
    turns:
      - user: "Book me a table for two tomorrow at 10am."
        expect:
          reply_contains_any: [booked, confirmed]
          tool_calls_include: [create_booking]

      - user: "Actually, can you move it to 11am instead?"
        expect:
          tool_calls_include: [update_booking]
          tool_calls_exclude: [create_booking]
          judge:
            rubric: >
              The reply confirms the new 11am time AND references the original
              10am booking, without asking the user to repeat information.
    ```

=== "conftest.py"

    ```python
    import pytest


    @pytest.fixture
    def llm_eval_agent():
        # Deterministic mock agent that remembers nothing but answers plausibly per turn.
        async def agent(history):
            message = history[-1]["content"].lower()
            if "11am" in message:
                return "Done — moved your booking from 10am to 11am. Reference stays BK-1234.", ["update_booking"]
            return "Booked for tomorrow at 10am. Reference BK-1234.", ["create_booking"]

        return agent
    ```

[Runnable project ↗](https://github.com/datarootsio/pytest-agent-eval/tree/main/examples/multi-turn-judge) · See [Evaluators](evaluators.md) for the judge rubric surface.

## tool-calls

Assertions on *which* tools the agent invoked — include, exclude, and order. Reach for this when the reply text is not enough and you need to verify the agent took the right actions: authenticate before fetching, never call a destructive tool, and do it all in sequence.

=== "evals/ordered_flow.yaml"

    ```yaml
    id: booking_tool_order
    threshold: 1.0
    runs: 1
    turns:
      - user: "Book me a table for two tomorrow at 10am."
        expect:
          tool_calls_include: [authenticate, fetch_availability, create_booking]
          tool_calls_ordered: true
          tool_calls_exclude: [cancel_booking]
    ```

=== "conftest.py"

    ```python
    import pytest


    @pytest.fixture
    def llm_eval_agent():
        async def agent(history):
            return (
                "You're booked! Reference BK-1234.",
                ["authenticate", "fetch_availability", "create_booking"],
            )

        return agent
    ```

[Runnable project ↗](https://github.com/datarootsio/pytest-agent-eval/tree/main/examples/tool-calls) · See [Evaluators](evaluators.md) for `ToolCallEvaluator`.

## tool-call-args

Goes one level deeper than `tool-calls`: it asserts on the *arguments* the agent passed. Reach for this when calling the right tool is not enough — the party size, date, and time have to be correct too. The example shows all three modes side by side: `subset` (default), `exact`, and an LLM-judged rubric over the call's JSON arguments. Note that the fixture returns `ToolCall(name, args)` objects rather than plain strings — that is what makes the arguments available to assert on.

=== "evals/booking_args.yaml"

    ```yaml
    id: booking_argument_checks
    threshold: 1.0
    runs: 1
    turns:
      - user: "Book me a table for two tomorrow at 10am."
        expect:
          tool_calls_include: [create_booking]
          tool_calls_args:
            # subset (default): these keys/values must appear; extras are fine
            - tool: create_booking
              args:
                time: 10am
                party_size: 2

            # exact: the full argument dict must match
            - tool: create_booking
              mode: exact
              args:
                time: 10am
                date: tomorrow
                party_size: 2

            # LLM-judged: rubric evaluated against the call's JSON arguments
            - tool: create_booking
              judge:
                rubric: "The booking time must be within business hours (9am-5pm)."
    ```

=== "conftest.py"

    ```python
    import pytest

    from pytest_agent_eval import ToolCall


    @pytest.fixture
    def llm_eval_agent():
        # Return ToolCall(name, args) instead of plain strings to enable argument assertions.
        async def agent(history):
            call = ToolCall("create_booking", {"time": "10am", "date": "tomorrow", "party_size": 2})
            return "Booked for two, tomorrow at 10am!", [call]

        return agent
    ```

[Runnable project ↗](https://github.com/datarootsio/pytest-agent-eval/tree/main/examples/tool-call-args) · See [Evaluators](evaluators.md) for the full `tool_calls_args` specification.

## regex-contains

Deterministic reply assertions: substring `all_of` plus regex matching. Reach for this when the reply must contain structured tokens — a reference number in a known format, a time, an order ID — that you can pin down with a pattern instead of paying for a judge.

=== "evals/reference_number.yaml"

    ```yaml
    id: booking_reference_format
    threshold: 1.0
    runs: 1
    turns:
      - user: "Book me a table for two tomorrow at 10am."
        expect:
          reply_contains_all: [confirmed, tomorrow]
          reply_matches_any:
            - "BK-\\d+"
            - "REF-\\d+"
          reply_matches_all:
            - "\\d{1,2}(am|pm)"
    ```

=== "conftest.py"

    ```python
    import pytest


    @pytest.fixture
    def llm_eval_agent():
        async def agent(history):
            return "Confirmed! Your reference number: BK-1234, tomorrow at 10am.", []

        return agent
    ```

[Runnable project ↗](https://github.com/datarootsio/pytest-agent-eval/tree/main/examples/regex-contains) · See [Evaluators](evaluators.md) for `ContainsEvaluator`.

## python-parametrize

The Python API instead of YAML, combined with `@pytest.mark.parametrize`. Reach for this when your eval cases are data-driven — one transcript shape run across many inputs (cities, locales, product IDs) — where hand-writing a YAML file per case would be repetitive. You get the full expressiveness of pytest: fixtures, marks, and parametrization.

The `agent_eval` argument is injected by the plugin's fixture; annotating it as `EvalSession` (from `pytest_agent_eval.runner`) makes that explicit and unlocks editor autocompletion for `.run(...)`. Because `from __future__ import annotations` defers annotation evaluation, the import lives under `TYPE_CHECKING` — it is only needed by type checkers and editors, never at runtime.

```python
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from pytest_agent_eval import Expect, Turn

if TYPE_CHECKING:
    from pytest_agent_eval.runner import EvalSession


@pytest.mark.parametrize("city", ["Ghent", "Leuven"])
@pytest.mark.agent_eval(threshold=1.0, runs=1)
async def test_booking_mentions_city(agent_eval: EvalSession, city: str) -> None:
    # Deterministic mock agent; replace with your real agent or an adapter.
    async def agent(history):
        return f"Booked a table in {city}! Reference BK-1234.", ["create_booking"]

    result = await agent_eval.run(
        agent=agent,
        turns=[
            Turn(
                user=f"Book me a table in {city} tomorrow at 10am.",
                expect=Expect(
                    reply_contains_all=[city],
                    tool_calls_include=["create_booking"],
                ),
            )
        ],
    )
    result.assert_threshold()
```

[Runnable project ↗](https://github.com/datarootsio/pytest-agent-eval/tree/main/examples/python-parametrize) · See the [Python API](python-api.md) for `Turn` and `Expect`.

## groups

Group-level pass thresholds with a per-group exit-code override. Reach for this when a whole suite should be judged as a set rather than test-by-test: allow a fraction of edge cases to fail while still gating the merge on a critical case that must always pass. Groups are configured in `pyproject.toml` and tag their transcripts.

=== "evals/happy_path.yaml"

    ```yaml
    id: booking_happy_path
    threshold: 1.0
    runs: 1
    tags: [gate:booking]
    turns:
      - user: "Book me a table for two tomorrow at 10am."
        expect:
          reply_contains_any: [confirmed, booked]
          tool_calls_include: [create_booking]
    ```

=== "evals/edge_case.yaml"

    ```yaml
    # This transcript fails on purpose: the group's 0.5 threshold absorbs it.
    id: booking_edge_case
    threshold: 1.0
    runs: 1
    tags: [gate:booking]
    turns:
      - user: "Book a gluten-free tasting menu for 11 people at sunrise."
        expect:
          reply_contains_any: [confirmed, booked]
          tool_calls_include: [create_booking]
    ```

=== "pyproject.toml"

    ```toml
    [tool.agent_eval]
    yaml_dirs = ["evals"]

    [tool.agent_eval.groups.booking]
    threshold = 0.5
    tags = ["gate:booking"]
    must_pass = ["booking_happy_path"]
    ```

=== "conftest.py"

    ```python
    import pytest


    @pytest.fixture
    def llm_eval_agent():
        # Handles the happy path, "fails" on the deliberately hard edge case.
        async def agent(history):
            message = history[-1]["content"].lower()
            if "gluten-free" in message:
                return "I'm not sure I can help with that.", []
            return "Booking confirmed! Reference BK-1234.", ["create_booking"]

        return agent
    ```

The `booking` group requires 50% of its `gate:booking` transcripts to pass, so the deliberately-failing `edge_case` is absorbed — but `must_pass` still forces `booking_happy_path` to pass regardless of the threshold.

[Runnable project ↗](https://github.com/datarootsio/pytest-agent-eval/tree/main/examples/groups) · See [Group thresholds](groups.md) for the full configuration surface.

## voice-livekit

Voice evals: each turn declares an `audio:` WAV that the `LiveKitAdapter` streams into a fresh LiveKit `AgentSession`; the tool calls and assistant transcript feed the same evaluators as a text agent. Reach for this when you are testing a real-time voice agent and want the same threshold-based scoring you use for text.

=== "evals/booking_voice.yaml"

    ```yaml
    id: booking_voice
    threshold: 1.0
    runs: 1
    turns:
      - user: "Book me a table for two tomorrow at 10am."
        audio: booking_t1.wav
        expect:
          reply_contains_any: [confirmed, booked]
    ```

=== "conftest.py"

    ```python
    import pytest

    from pytest_agent_eval.adapters.livekit import LiveKitAdapter


    def make_session():
        # Imported inside the factory so collection works without live credentials.
        from livekit.agents.voice import Agent, AgentSession
        from livekit.plugins import openai

        session = AgentSession(llm=openai.realtime.RealtimeModel())
        agent = Agent(instructions="You are a friendly booking assistant.", tools=[])
        return session, agent


    @pytest.fixture
    def llm_eval_agent():
        return LiveKitAdapter(make_session)
    ```

The WAV fixtures are generated from each turn's user text (hash-cached, idempotent) before running the suite:

```bash
python -m pytest_agent_eval.synthesize_audio
```

[Runnable project ↗](https://github.com/datarootsio/pytest-agent-eval/tree/main/examples/voice-livekit) · See the [LiveKit adapter docs](adapters.md#livekit-voice) for full options.
