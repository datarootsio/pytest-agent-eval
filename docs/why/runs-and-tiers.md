# Sample the distribution. Then assert in *tiers*.

The main idea of `pytest-agent-eval` is first to run the function more than once, and what's the percentage
of acceptable answers. The next question is "how do we measure an acceptable answer?"

```python
# tests/test_booking.py

import pytest
from pytest_agent_eval import Expect, Turn

@pytest.mark.agent_eval(runs=3, threshold=0.66)
async def test_booking_confirmation(agent_eval, booking_agent):
    result = await agent_eval.run(
        agent=booking_agent,
        turns=[
            Turn(
                user="book me a slot tomorrow at 10am",
                expect=Expect(reply_contains_any=["confirmed", "booked"]),
            )
        ],
    )
    result.assert_threshold()
```

<figure class="why-cast">
<div class="why-cast-mount"
     data-cast-id=""
     data-cast-slug="03-runs-and-threshold"
     data-cast-poster="npt:0:02"
     role="img"
     aria-label="A pytest run with runs=3 and threshold=0.66. Plain -vv reports only that one test passed; adding -rP reveals the per-run detail, where run 2 of 3 failed and the test still passes at score 0.67."></div>
<figcaption>asciinema: <code>pytest --agent-eval-live -vv</code>, then again with <code>-rP</code></figcaption>
</figure>

??? note "Transcript"

    ```console
    $ pytest --agent-eval-live -vv
    tests/test_booking.py::test_booking_confirmation PASSED                  [100%]

    ============================== 1 passed in 0.01s ===============================

    $ pytest --agent-eval-live -vv -rP
    tests/test_booking.py::test_booking_confirmation PASSED                  [100%]

    ==================================== PASSES ====================================
    __________________________ test_booking_confirmation ___________________________
    ----------------------------------- LLM Eval -----------------------------------
    [2/3 runs, score=0.67 >= 0.66]
      Run 1 ✅
        All substring and pattern checks passed
      Run 2 ❌
        Reply did not contain any of ['confirmed', 'booked']
      Run 3 ✅
        All substring and pattern checks passed
    ============================== 1 passed in 0.01s ===============================
    ```

!!! note "Why `-rP` and not just `-vv`"

    pytest only prints a report section for a test that **failed**. A passing eval's
    per-run detail is recorded either way, but you have to ask for it: `-rP` is pytest's
    "report passed tests too". Without it, the run above is the single word `PASSED` — which
    is precisely the problem this page is about, one bit where you wanted a distribution.

<figure class="why-fig">
<div class="why-fig-scroll">
<svg viewBox="0 0 760 262" role="img" aria-label="Three tiers of assertion ordered by cost: deterministic string checks at the bottom at zero cost, structural tool-call checks in the middle also at zero cost, and a semantic LLM judge on top at roughly two seconds and one cent per run">
  <text class="s-lbl" x="8" y="14">TIER</text>
  <text class="s-lbl" x="250" y="14">WHAT IT ASSERTS</text>
  <text class="s-lbl" x="576" y="14">COST / RUN</text>

  <rect x="8" y="24" width="700" height="58" rx="8" fill="var(--why-amber-soft)" stroke="var(--why-amber)" stroke-width="1.4"/>
  <text class="s-node" x="24" y="48" fill="var(--why-amber)">semantic</text>
  <text class="s-lbl" x="24" y="66">a rubric, graded</text>
  <text class="s-lbl-strong" x="250" y="48">tone, completeness, reasoning</text>
  <text class="s-lbl" x="250" y="66">an LLM judges the reply against words you wrote</text>
  <text class="s-lbl-strong" x="576" y="48" fill="var(--why-amber)">~2 s · $0.01</text>
  <text class="s-lbl" x="576" y="66">variance: high</text>

  <rect x="8" y="90" width="700" height="58" rx="8" fill="var(--why-accent-soft)" stroke="var(--why-accent)" stroke-width="1.8"/>
  <text class="s-node" x="24" y="114" fill="var(--why-accent)">structural</text>
  <text class="s-lbl" x="24" y="132">what it did</text>
  <text class="s-lbl-strong" x="250" y="114">which tools ran, in what order, with what args</text>
  <text class="s-lbl" x="250" y="132" fill="var(--why-accent)">▸ the whole of the next page</text>
  <text class="s-lbl-strong" x="576" y="114" fill="var(--why-accent)">0 ms · $0</text>
  <text class="s-lbl" x="576" y="132">variance: none</text>

  <rect x="8" y="156" width="700" height="58" rx="8" fill="var(--why-green-soft)" stroke="var(--why-green)" stroke-width="1.4"/>
  <text class="s-node" x="24" y="180" fill="var(--why-green)">deterministic</text>
  <text class="s-lbl" x="24" y="198">what it said</text>
  <text class="s-lbl-strong" x="250" y="180">substrings and regex over the reply</text>
  <text class="s-lbl" x="250" y="198">the same <tspan font-weight="600">assert</tspan> you already write</text>
  <text class="s-lbl-strong" x="576" y="180" fill="var(--why-green)">0 ms · $0</text>
  <text class="s-lbl" x="576" y="198">variance: none</text>

  <path class="s-arrow" d="M726 208 V44"/>
  <path d="M721 50 l5 -7 l5 7" fill="none" stroke="var(--md-default-fg-color--light)" stroke-width="1.5"/>
  <text class="s-lbl" x="740" y="126" transform="rotate(-90 740 126)" text-anchor="middle">cost &amp; variance</text>

  <path class="s-arrow" d="M300 226 V246" stroke="var(--why-green)"/>
  <path d="M295 240 l5 7 l5 -7" fill="none" stroke="var(--why-green)" stroke-width="1.5"/>
  <text class="s-note" x="8" y="244" fill="var(--why-green)">Push every check down.</text>
  <text class="s-note" x="322" y="244">A judge is a last resort, not a default.</text>
</svg>
</div>
<figcaption>svg: the three tiers, cheapest first</figcaption>
</figure>

## Look at distributions and distribute asserts in tiers

If a single sample cannot answer the question, take several and assert on the rate. `runs=3`
with `threshold=0.66` says: run the whole transcript three times, pass if two of them do. The
`Run 2 ❌` in that output is the point, sitting under a test pytest reports as `PASSED`: a
test that fails a third of the time is now a **passing** test, on purpose.

The second half is what you assert on each run, and there are only three kinds. Exact string
checks on what it *said*. Structural checks on what it *did*. And a graded rubric for the things
that genuinely need taste. They cost wildly different amounts and they compose freely on the same
turn.

Ideally, a good test suite covers all tiers, where deterministic tests are more reproducible and cheap and can be run often.

## Go deeper

- [Evaluators](../evaluators.md): every evaluator and how they compose
- [Python API](../python-api.md): the `agent_eval` fixture, `Turn`, `Expect`, `runs`, `threshold`
- [Reporting](../reporting.md): `-v`, `-vv`, and the markdown report
