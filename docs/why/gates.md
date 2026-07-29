# Gates and statistics

<figure class="why-fig">
<div class="why-fig-scroll">
<svg viewBox="0 0 760 236" role="img" aria-label="A group of ten evals, nine green and one red, measured against a ninety percent threshold, with booking_confirmation pinned as must_pass, the group passes and the exit code is overridden to zero">
  <rect x="8" y="22" width="700" height="118" rx="10" fill="var(--md-code-bg-color)" stroke="var(--md-default-fg-color--lighter)" stroke-width="1.5"/>
  <text class="s-lbl" x="24" y="44">[tool.agent_eval.groups.booking]  tags = ["gate:booking"]</text>

  <rect x="24" y="58" width="58" height="22" rx="4" fill="var(--why-green-soft)" stroke="var(--why-green)"/>
  <rect x="90" y="58" width="58" height="22" rx="4" fill="var(--why-green-soft)" stroke="var(--why-green)"/>
  <rect x="156" y="58" width="58" height="22" rx="4" fill="var(--why-green-soft)" stroke="var(--why-green)"/>
  <rect x="222" y="58" width="58" height="22" rx="4" fill="var(--why-green-soft)" stroke="var(--why-green)"/>
  <rect x="288" y="58" width="58" height="22" rx="4" fill="var(--why-green-soft)" stroke="var(--why-green)"/>
  <rect x="354" y="58" width="58" height="22" rx="4" fill="var(--why-green-soft)" stroke="var(--why-green)"/>
  <rect x="420" y="58" width="58" height="22" rx="4" fill="var(--why-green-soft)" stroke="var(--why-green)"/>
  <rect x="486" y="58" width="58" height="22" rx="4" fill="var(--why-green-soft)" stroke="var(--why-green)"/>
  <rect x="552" y="58" width="58" height="22" rx="4" fill="var(--why-red-soft)" stroke="var(--why-red)"/>
  <rect x="618" y="58" width="58" height="22" rx="4" fill="var(--why-green-soft)" stroke="var(--why-green)"/>

  <text class="s-lbl" x="552" y="98" fill="var(--why-red)">edge_case</text>
  <text class="s-lbl" x="24" y="98" fill="var(--why-amber)">▲ must_pass</text>
  <text class="s-lbl" x="24" y="112">booking_confirmation</text>

  <text class="s-lbl-strong" x="420" y="126">9 / 10 = 90%</text>
  <text class="s-lbl" x="510" y="126">≥ 90% required</text>
  <text class="s-lbl-strong" x="640" y="126" fill="var(--why-green)">PASSED</text>

  <line class="s-rule" x1="8" y1="160" x2="708" y2="160"/>
  <text class="s-lbl-strong" x="8" y="184" fill="var(--why-amber)">exit code 0</text>
  <text class="s-lbl" x="104" y="184">failure absorbed by the gate, still printed in the summary</text>
  <text class="s-note" x="8" y="214">Three runs is not a hypothesis test. It is a tripwire, and gates are where the power comes back.</text>
</svg>
</div>
<figcaption>svg: a group threshold with a <code>must_pass</code> pin</figcaption>
</figure>

```toml
# pyproject.toml

[tool.agent_eval.groups.booking]
threshold = 0.9                          # 90% of matched tests must pass
tags = ["gate:booking"]                  # match transcripts by tag
must_pass = ["booking_confirmation"]     # this one must individually pass

[tool.agent_eval.groups.smoke]
tags = ["smoke"]                         # threshold defaults to 1.0
```

```console
============================== group summary ===============================
booking: 9/10 passed (90%) >= 90% required -- PASSED
  failures: booking_edge_case
  must_pass: booking_confirmation ok
smoke:   4/4 passed (100%) >= 100% required -- PASSED
exit code overridden to 0: all group thresholds met

$ echo $?
0
```

## Predictability vs. flexibility

A suite of probabilistic tests may fail *somewhere* almost every run. We may test for specific words, but
we cannot cover all possible combinations (or would be extremely expensive). The idea is that the 90% that
passes gives us enough indication that the remaining 10% is "ok". If any red turns CI red, you
will be dealing with many false positives. So gate on the aggregate: 90% of booking
evals must pass, **with specific ones must pass individually**. Everything else may
flicker, and every failure is still printed.

One may argue that: **three runs at 66% is not statistically significant.** Correct.
It is not a hypothesis test and should not be read as one: you are not estimating a true pass
rate, you are placing a tripwire that catches large regressions cheaply.

However, a gate over forty evals aggregates hundreds of runs, and *that* number moves
meaningfully when something breaks. Per-test thresholds suppress noise; the group
gate is the number you actually trust.

## Go deeper

- [Group thresholds](../groups.md): membership, `must_pass`, the exit-code override
- [Reporting](../reporting.md): the `## Groups` section of the markdown report
