# Some things only a rubric can check

At times, only a semantic check is enough to verify correctness. What the agent *did* is a tool call.
But some of what you care about is neither a substring nor a tool call.
Whether the reply actually answered the question. Whether it stayed on the booking the user
already made instead of quietly starting a new one. Whether it asked the user to repeat something
they had already said. Whether it used a specific tone of voice. These are judgements, and the top
tier of the stack is where you make them: you write the standard down as a **rubric**, and another
model grades the reply against it. This is commonly referred as **LLM-as-a-Judge.**

## The rubric is the test

```python
# tests/test_reschedule.py

import pytest
from pytest_agent_eval import Expect, JudgeEvaluator, Turn

RESCHEDULE_RUBRIC = """
The reply must:
  - state the new time explicitly
  - repeat the existing booking reference, unchanged
The reply must not:
  - invent or alter a reference number
  - ask the user to repeat information they have already given
"""

@pytest.mark.agent_eval(runs=3, threshold=0.66)
async def test_reschedule_reads_well(agent_eval, booking_agent):
    result = await agent_eval.run(
        agent=booking_agent,
        turns=[
            Turn(user="Book me a slot tomorrow at 10am."),
            Turn(
                user="Actually make it 11am.",
                expect=Expect(
                    tool_calls_include=["update_booking"],
                    evaluators=[JudgeEvaluator(rubric=RESCHEDULE_RUBRIC)],
                ),
            ),
        ],
    )
    result.assert_threshold()
```

Note what the judge is *not* asked. It is not asked whether the booking moved: that is
`tool_calls_include`, on the same turn, for free. The rubric only covers the part no string check
can reach.

A rubric earns its keep by being specific enough to disagree with. "The reply must be helpful"
grades nothing. Naming the required facts, and naming the failure modes you have actually seen,
gives the judge something to check and gives you a verdict you can act on.

## What comes back is a verdict and its reasoning

```console
$ pytest --agent-eval-live -vv tests/test_reschedule.py

tests/test_reschedule.py::test_reschedule_reads_well PASSED
  ---- LLM Eval ----
  [2/3 runs, score=0.67 >= 0.66]
    Run 1 ✅
    States 11am and repeats BK-1234 unchanged. No repeated questions.
    Run 2 ❌
    Confirms the change but never states the new time, so the first requirement fails.
    Run 3 ✅
    New time given as 11am, reference BK-1234 carried over, nothing re-asked.

1 passed in 12.08s
```

That second line exemplifies when you may need a judge. A substring check that
fails tells you a string was absent. A judge tells you **which clause of your rubric the reply
broke**, in the reply's own terms, which is usually the sentence you would have had to write
yourself while debugging.

<figure class="why-fig">
<div class="why-fig-scroll">
<svg viewBox="0 0 760 220" role="img" aria-label="What the judge receives and returns: the rubric, the conversation history with the user turn, and the agent reply all feed one judge model call, which returns a boolean verdict and a reasoning string">
  <text class="s-lbl" x="8" y="14">ONE JUDGE CALL, PER RUN, PER TURN</text>

  <rect x="8" y="26" width="200" height="46" rx="8" class="s-box"/>
  <text class="s-node" x="20" y="46">rubric</text>
  <text class="s-lbl" x="20" y="62">the words you wrote</text>

  <rect x="8" y="84" width="200" height="46" rx="8" class="s-box"/>
  <text class="s-node" x="20" y="104">history + user turn</text>
  <text class="s-lbl" x="20" y="120">the conversation so far</text>

  <rect x="8" y="142" width="200" height="46" rx="8" class="s-box"/>
  <text class="s-node" x="20" y="162">agent reply</text>
  <text class="s-lbl" x="20" y="178">this turn's output</text>

  <path class="s-arrow" d="M208 49 C 244 49, 244 100, 276 100"/>
  <path class="s-arrow" d="M208 107 H276"/>
  <path class="s-arrow" d="M208 165 C 244 165, 244 114, 276 114"/>
  <path class="s-arrow" d="M270 102 l6 5 l-6 5" fill="var(--md-default-fg-color--light)"/>

  <rect x="280" y="84" width="170" height="46" rx="8" fill="var(--why-amber-soft)" stroke="var(--why-amber)" stroke-width="1.6"/>
  <text class="s-node" x="292" y="104" fill="var(--why-amber)">judge model</text>
  <text class="s-lbl" x="292" y="120">~2 s · $0.01</text>

  <path class="s-arrow" d="M450 107 H500"/>
  <path class="s-arrow" d="M500 107 C 512 107, 512 82, 524 82"/>
  <path class="s-arrow" d="M500 107 C 512 107, 512 132, 524 132"/>
  <path class="s-arrow" d="M518 77 l6 5 l-6 5" fill="var(--md-default-fg-color--light)"/>
  <path class="s-arrow" d="M518 127 l6 5 l-6 5" fill="var(--md-default-fg-color--light)"/>

  <rect x="528" y="60" width="222" height="44" rx="8" class="s-box"/>
  <text class="s-node" x="540" y="80">passed: bool</text>
  <text class="s-lbl" x="540" y="96">counts toward the threshold</text>

  <rect x="528" y="112" width="222" height="44" rx="8" class="s-box"/>
  <text class="s-node" x="540" y="132">reasoning: str</text>
  <text class="s-lbl" x="540" y="148">printed at -vv, in the report</text>

  <line class="s-rule" x1="8" y1="196" x2="752" y2="196"/>
  <text class="s-note" x="8" y="212">The judge is itself a sample. That is why it sits at the top of the cost stack, not the bottom.</text>
</svg>
</div>
<figcaption>svg: what one judge call receives and returns</figcaption>
</figure>

## Judging arguments, not just the answer

The same idea applies one level in. Some constraints on a tool's arguments are awkward to write as
exact values, and that is what `ToolCallArgsJudgeEvaluator` is for:

```python
from pytest_agent_eval import ToolCallArgsJudgeEvaluator

ToolCallArgsJudgeEvaluator(
    tool="create_booking",
    rubric="The requested time must fall within business hours, 9am to 6pm.",
)
```

It short-circuits before spending anything: if the tool was never called, or was called without
captured arguments, the evaluator fails with a precise message and no judge call is made. Only a
real set of arguments reaches the model.

## The costs and risks of a judge

A judge is an LLM call, which means everything from [where LLMs break](why-it-breaks.md) applies to
the judge as well as the agent. It is not a referee standing outside the system. It is a second
probabilistic component you have added to your test, and it brings three costs with it.

It is **slow and metered**: seconds and cents on every run of every turn that uses it, multiplied
by `runs` (`pytest-agent-eval` also supports parallel execution to reduce the wall time).
It has **its own variance**: the same reply and the same rubric can be graded differently,
which is a second reason `runs` and `threshold` exist rather than a nuisance on top of them. And it
can **fail outright**; when the API is unreachable the evaluator returns a failing verdict whose
reasoning says so, rather than taking the whole session down with it.

None of that argues against judges. It argues for using them on exactly the questions that need
taste, and for reaching first for the two tiers that cost nothing extra. If you find yourself writing a
rubric that says "the reply must contain a reference number", you have written
`reply_matches_any=[r"BK-\d+"]` the expensive way.

!!! tip "Judge tests"

    When we are talking about LLM testing, we need to think in terms of probabilities
    that the outcomes are aligned with what we expect. LLMs may not be perfect
    all the time,including Judges. Tests increases our confidence that nothing will
    break, but they cannot guarantee it.

## Go deeper

- [Evaluators](../evaluators.md): `JudgeEvaluator`, `ToolCallArgsJudgeEvaluator`, and writing your own
- [Configuration](../configuration.md): `model`, `judge_model`, `retries`, `timeout`
- [Reporting](../reporting.md): where the judge's reasoning is kept
