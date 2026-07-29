# The agent wrote the agent. It *looked* right.

<figure class="why-fig">
<div class="why-fig-scroll">
<svg viewBox="0 0 720 176" role="img" aria-label="A trace of the generated agent: authenticate, fetch_availability, then create_booking twice — while the assertion on the reply still reports PASSED">
  <text class="s-lbl" x="0" y="12">TRACE — "book me a slot tomorrow at 10am"</text>
  <line class="s-arrow" x1="14" y1="34" x2="14" y2="150" stroke-dasharray="3 4"/>
  <circle cx="14" cy="46" r="4" fill="var(--why-green)"/>
  <text class="s-lbl-strong" x="30" y="50">authenticate</text>
  <text class="s-lbl" x="150" y="50">ok</text>
  <circle cx="14" cy="78" r="4" fill="var(--why-green)"/>
  <text class="s-lbl-strong" x="30" y="82">fetch_availability</text>
  <text class="s-lbl" x="180" y="82">3 slots</text>
  <circle cx="14" cy="110" r="4" fill="var(--why-green)"/>
  <text class="s-lbl-strong" x="30" y="114">create_booking</text>
  <text class="s-lbl" x="163" y="114">BK-4417</text>
  <circle cx="14" cy="142" r="4" fill="var(--why-red)"/>
  <text class="s-lbl-strong" x="30" y="146" fill="var(--why-red)">create_booking</text>
  <text class="s-lbl" x="163" y="146" fill="var(--why-red)">BK-4418</text>
  <path class="s-brace" d="M300 104 q10 0 10 10 q0 10 10 10 q-10 0 -10 10 q0 10 -10 10" stroke="var(--why-red)"/>
  <text class="s-note" x="330" y="132" fill="var(--why-red)">booked twice — and the reply says "confirmed"</text>
  <rect x="470" y="30" width="240" height="52" rx="8" class="s-box"/>
  <text class="s-lbl" x="484" y="50">assert "confirmed" in reply</text>
  <text class="s-lbl-strong" x="484" y="70" fill="var(--why-green)">PASSED</text>
</svg>
</div>
<figcaption>svg — one request, four tool calls, a green test</figcaption>
</figure>

Recording pending: `beat-01-broken-agent.cast` — target 1:40, 90 cols.

```console
$ claude
> build me a booking agent with pydantic-ai and write a test for it

  …creating agent.py
  …creating test_booking.py

$ pytest -q
.                                                          [100%]
1 passed in 3.41s

$ sqlite3 bookings.db "select count(*) from bookings"
2
```

## The argument

The agent produced working code and a passing test in under a minute. The test asserts that
the reply contains the word "confirmed". The reply does contain the word "confirmed". The test
is green, and the customer has been booked into the same slot twice.

Nothing here is a failure of the model. It is a failure of the **assertion**. We asked whether
the agent said the right thing, when what we cared about was whether it *did* the right thing —
and no amount of extra prompting fixes a question aimed at the wrong target.

Writing agents got dramatically cheaper this year. Knowing whether they still work did not.
That gap is what the rest of these pages are about.

## Go deeper

- [Getting started](../getting-started.md) — install, configure, and run your first eval
- [Examples](../examples.md) — a runnable project per feature
