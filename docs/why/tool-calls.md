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

```console
$ pytest --agent-eval-live -vv tests/test_reschedule.py

tests/test_reschedule.py::test_reschedule_flow FAILED
  ---- LLM Eval ----
  [0/3 runs, score=0.00 < 0.80]
    Run 1 ❌  turn 2:
      ✅ tool_calls_include  [update_booking]
      ❌ tool_calls_exclude  create_booking was called

# the reply said "I've moved your booking to 11am." It was perfect.
# it made a second booking instead of moving the first.
```

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

:   **in what order**: `authenticate` before `create_booking`, always

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
