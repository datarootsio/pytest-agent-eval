# For an agent, the reply is the *least* interesting output

!!! info "The middle tier, claimed"

    This is the **structural** row from [the previous page](runs-and-tiers.md), in full. It is the
    tier that barely existed before agents — and the reason it sits next to the cheap
    deterministic checks rather than up with the judge is that **a tool call is a string**.

Recording pending: `beat-06-toolcalls.cast` — target 0:40, 90 cols.

```console
$ pytest --agent-eval-live -vv tests/evals/reschedule.yaml

reschedule_flow FAILED
  ---- LLM Eval ----
  [0/3 runs, score=0.00 < 0.80]
    Run 1 ❌  turn 2:
      ✅ tool_calls_include  [update_booking]
      ❌ tool_calls_exclude  create_booking was called
      ❌ tool_calls_args     create_booking(time='11am')
                              expected: no call at all

# the reply said "I've moved your booking to 11am." It was perfect.
# it made a second booking instead of moving the first.
```

```python
call = ToolCall("create_booking", {"time": "11am"})

call == "create_booking"   # True — it is a str
call.args["time"]          # "11am"
```

`tool_calls_include`

:   **which** tools ran

`tool_calls_ordered`

:   **in what order** — `authenticate` before `create_booking`, always

`tool_calls_args`

:   **with what arguments** — subset by default, `mode: exact` for equality

`tool_calls_exclude`

:   **and what must never run** — `cancel_booking`, `refund`

## The argument

Here is the turn these pages have been walking toward. The reply on that failing run was flawless
prose — and the agent double-booked the customer, exactly as it did on
[the first page](index.md). The prose was never the thing worth asserting on.

Which means agents made testing **easier** in one specific, underrated way: their behaviour
became *observable*. A tool call is a discrete, ordered, structured record of what the agent
actually did — and because `ToolCall` subclasses `str`, checking one costs exactly what checking a
substring costs. Nothing. That is why the middle tier sits beside the cheap tier and not beside
the judge.

So the rule from the last page gets sharper. Do not ask a judge whether the agent booked the
slot. Ask whether `create_booking` ran *once*, after `authenticate`, with `time="11am"`.

## Go deeper

- [Evaluators](../evaluators.md) — `ToolCallEvaluator`, `ToolCallArgsEvaluator`
- [YAML API](../yaml-api.md) — `tool_calls_args`, `mode: exact`
- [API reference — Models](../api-reference/models.md) — `ToolCall` and its `.args`
