# Sample the distribution. Then assert in *tiers*.

Recording pending: `beat-05-threshold.cast` — target 0:30, 90 cols.

```console
$ pytest --agent-eval-live -vv

tests/evals/booking.yaml::booking_confirmation PASSED
  ---- LLM Eval ----
  [2/3 runs, score=0.67 >= 0.66]
    Run 1 ✅  all substring checks passed · all tool call checks passed
    Run 2 ❌  reply_contains_any: none of ['confirmed','booked'] found
    Run 3 ✅  all substring checks passed · all tool call checks passed

1 passed in 12.08s
```

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
<figcaption>svg — the three tiers, cheapest first</figcaption>
</figure>

## The argument

If a single sample cannot answer the question, take several and assert on the rate. `runs: 3`
with `threshold: 0.66` says: run the whole transcript three times, pass if two of them do. The
amber line in that output is the point — a test that fails a third of the time is now a
**passing** test, on purpose.

The second half is what you assert on each run, and there are only three kinds. Exact string
checks on what it *said*. Structural checks on what it *did*. And a graded rubric for the things
that genuinely need taste. They cost wildly different amounts and they compose freely on the same
turn.

One rule follows: **push every check as far down that stack as it will go.** Most rubrics people
reach for are a string check that hasn't been thought through yet — and the middle tier, which is
where agents actually live, is [the next page](tool-calls.md).

## Go deeper

- [Evaluators](../evaluators.md) — every evaluator and how they compose
- [YAML API](../yaml-api.md) — `runs`, `threshold`, `turns`
- [Reporting](../reporting.md) — `-v`, `-vv`, and the markdown report
