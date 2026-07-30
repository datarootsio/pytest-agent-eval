# For an agent, the reply is the *least* interesting output

!!! info "The middle tier"

    This is the **structural** row from [the previous page](runs-and-tiers.md). It is the tier
    that did not exist before agents, and the reason it sits next to the cheap
    deterministic checks rather than up with the judge is that **a tool call is identified
    by a string**.

```python
# tests/test_reschedule.py

import pytest
from pytest_agent_eval import Expect, Turn

@pytest.mark.agent_eval(runs=3, threshold=0.8)
async def test_reschedule_flow(agent_eval, booking_agent):
    result = await agent_eval.run(
        agent=booking_agent,
        turns=[
            Turn(
                user="Book me a slot tomorrow at 10am.",
                expect=Expect(tool_calls_include=["create_booking"]),
            ),
            Turn(
                user="Actually make it 11am.",
                expect=Expect(
                    tool_calls_include=["update_booking"],
                    tool_calls_exclude=["create_booking"],
                ),
            ),
        ],
    )
    result.assert_threshold()
```

<figure class="why-cast">
<div class="why-cast-mount"
     data-cast-id=""
     data-cast-slug="04-tool-calls-fail"
     data-cast-poster="npt:0:02"
     role="img"
     aria-label="A three-run eval that fails every run at score 0.00. The reply is correct each time; what fails is tool_calls_exclude, because the agent called create_booking a second time as well as moving the existing booking."></div>
<figcaption>asciinema: <code>tool_calls_exclude</code> catching a second booking</figcaption>
</figure>

??? note "Transcript"

    ```console
    $ pytest --agent-eval-live -vv tests/test_reschedule.py
    tests/test_reschedule.py::test_reschedule_flow FAILED                    [100%]

    =================================== FAILURES ===================================
    _____________________________ test_reschedule_flow _____________________________
    ...
    E           AssertionError: LLM eval failed: score=0.00 < threshold=0.80 (0/3 runs passed)

    ../../../src/pytest_agent_eval/models.py:278: AssertionError
    ----------------------------------- LLM Eval -----------------------------------
    [0/3 runs, score=0.00 < 0.80]
      Run 1 ❌
        All tool call checks passed
        Forbidden tool 'create_booking' was called
      Run 2 ❌
        All tool call checks passed
        Forbidden tool 'create_booking' was called
      Run 3 ❌
        All tool call checks passed
        Forbidden tool 'create_booking' was called
    =========================== short test summary info ============================
    FAILED tests/test_reschedule.py::test_reschedule_flow - AssertionError: LLM eval failed: score=0.00 < threshold=0.80 (0/3 runs passed)
    ============================== 1 failed in 0.08s ===============================
    ```

The reply was perfect — *"I've moved your booking to 11am."* — and all three runs fail anyway.
What the agent actually did was move the booking *and* create a second one, and
`tool_calls_exclude` is the check that saw it. You can read that off the output too: turn 2
also asserts `tool_calls_include=["update_booking"]`, and a single evaluator reports every
failure it finds, so an absent `update_booking` would have printed its own line beside the
forbidden one. Only `create_booking` is named — which means the move happened as well.

Read the two lines under each run as the two turns, in order: the report flattens every turn's
reasoning into one flat list and does not label which turn each line came from. `All tool call
checks passed` is turn 1 booking the 10am slot; `Forbidden tool 'create_booking' was called` is
turn 2. It is not one turn that somehow both passed and failed.

```python
from pytest_agent_eval import ToolCall

call = ToolCall("create_booking", {"time": "11am"})

call == "create_booking"   # True
call.args["time"]          # "11am"
```

Arguments are Python dictionaries, so asserting on them stays deterministic too: no model call, the
same zero cost as the name checks.

```python
from pytest_agent_eval import ToolCallArgsEvaluator

# subset (the default): only the keys you name are checked
ToolCallArgsEvaluator(tool="update_booking", args={"time": "11am"})

# exact: the captured arguments must equal this dict
ToolCallArgsEvaluator(tool="update_booking", args={"time": "11am"}, mode="exact")
```

If the tool ran more than once in the turn, the assertion passes when any call matches. It does need
the arguments to have been captured: the bundled adapters do that for you, and a hand-written agent
returns `ToolCall(name, args)` instead of a plain string.

`tool_calls_include`

:   **which** tools ran

`tool_calls_ordered`

:   **in what order**: a bool that makes `tool_calls_include` order-sensitive, so
    `authenticate` must appear before `create_booking`

`tool_calls_args`

:   **with what arguments**: subset by default, `mode="exact"` for equality

`tool_calls_exclude`

:   **and what must never run**: `cancel_booking`, `refund`

## Inspecting tool calls gives us insight on the internals

Agents made testing **easier** in one specific, underrated way: their behaviour
became *observable*. A tool call is a discrete, ordered, structured record of what the agent
actually did, and because `ToolCall` is identified across providers as a `str`, checking one
costs exactly what checking a substring costs. Nothing. That is why the middle tier is cheaper than the judge.

Instead of asking a judge whether the agent booked the slot, we can ask whether `create_booking` ran
*once*, after `authenticate`, with `time="11am"`.

## Go deeper

- [Evaluators](../evaluators.md): `ToolCallEvaluator`, `ToolCallArgsEvaluator`
- [Python API](../python-api.md): `tool_calls_args`, `mode="exact"`
- [API reference, Models](../api-reference/models.md): `ToolCall` and its `.args`
