# Learn tab — "Why agent evals"

**Status:** design approved, not yet implemented
**Date:** 2026-07-29
**Visual reference:** <https://claude.ai/code/artifact/21018351-8c7d-464d-b251-5d74bcee339f>

## Summary

Add a second top-level tab to the docs site — **Learn**, alongside **Docs** — containing a
ten-page narrative that argues why agent evals are necessary and how this package answers
that. The same pages are the source for a 20–30 minute conference talk.

The docs have no "why" content today: `docs/index.md` goes from tagline to `pip install` in
three lines, and there are no visuals anywhere in the site. The talk assets (five diagrams,
eight terminal recordings) are the thing the docs are missing regardless of whether the talk
is ever given again. That is the justification for the effort.

## Decisions

These are settled. Each is recorded with the reason, because the reasons constrain
implementation.

| Decision | Reason |
|---|---|
| A separate **Learn** tab, FastAPI/SQLModel style | The narrative is read in order; reference docs are not. Mixing them makes both worse. |
| **Nothing moves.** Docs tab keeps its exact current nav | Zero broken links, no muscle-memory reset. Learn's last page links across to Getting started. |
| Pages **must stand alone** for a reader without the speaker | The section is a permanent docs asset, not talk scaffolding. |
| **No present/read mode switch** | One register. Claims are sized to work read at a desk *and* projected; the speaker scrolls past the prose. |
| Beat 1 is a **live screen share in a separate window**, not a page cast | It is the opener and it needs to be live. An asciinema insurance take exists as a fallback. |
| **All** screen recordings are asciinema | Rules out GUI demos — notably editor autocomplete from the JSON Schema, which becomes prose. |
| **One purpose-built booking agent** for every cast | Continuity. The room learns one domain in beat 1 and never re-learns it. |
| Talk-first build order; zone-4 prose backfilled after | The date is near. See [Build order](#build-order). |
| Learn joins the published nav **only when prose lands** | Publishing sparse pages would violate the stand-alone requirement above. |

### Audience

Mixed technical: data scientists, ML engineers, some non-Python. Three consequences that are
baked into the beat list and must not be optimised away:

1. **Beats 2 and 3 are real content, not filler.** A significant part of the room works in
   notebooks without a test suite. "Why anyone writes tests" and "what a test is in pytest"
   earn their five combined minutes.
2. **"Sample, not distribution" is the spine.** This audience is already fluent in it. Said in
   those words, the entire runs/threshold model lands in one sentence.
3. **Beat 7 exists because of this audience.** They will object that three runs at 66% is not
   significant. Answering it pre-emptively is the highest-credibility minute in the talk;
   burying it inside beat 5 wastes it.

## Information architecture

Enabling tabs is **not** an additive change. `zensical.toml` currently sets
`navigation.sections` and has no `navigation.tabs`; turning tabs on requires assigning all
seven existing top-level nav entries to a tab. The assignment is:

- **Docs** — Home, Getting started, Examples, Writing evals, Running & CI, Using with coding
  agents, API reference. Unchanged in content and order.
- **Learn** — the ten narrative pages, in `docs/learn/`.

Tab bar order is **Docs, Learn**. `docs/index.md` stays the site root and stays under Docs;
Learn does not displace it.

## Page anatomy

Every Learn page has the same five zones, top to bottom. The order is the design: a reader
gets the argument, a presenter stays in zones 1–3.

1. **Claim** — one room-legible line. `clamp()`-sized so it reads at a desk and projects.
2. **One SVG** — carries exactly one idea. Theme-aware via CSS custom properties.
3. **One cast** — asciinema, 20–50s, one idea.
4. **Argument** — 120–180 words that make the point unaided. Set in a serif to separate it
   from the slide-shaped zones above.
5. **Go deeper** — two or three links into the Docs tab.

Zones 2 and 3 are both optional per page; zones 1, 4 and 5 are mandatory.

**Presenting discipline:** never read zone 4 aloud. That is what blows the clock.

## The ten beats

Total 30 minutes. Cut levers listed after the table.

| # | Page | Claim | SVG | Cast | Min |
|---|---|---|---|---|---|
| 1 | `index.md` | The agent wrote the agent. It *looked* right. | double-booking trace (optional) | live screen share + insurance take | 3 |
| 2 | `why-tests.md` | Tests aren't about correctness. They're about change. | commit timeline, regression caught | — | 2 |
| 3 | `what-is-a-test.md` | What a test *is*, in pytest | four properties pipeline | pytest basics, assertion rewriting | 4 |
| 4 | `why-it-breaks.md` | All four break at once | same pipeline, broken | the flake, 5 runs 2 red | 4 |
| 5 | `runs-and-tiers.md` | Sample the distribution. Then assert in tiers. | three tiers | `runs=3 threshold=0.66` at `-vv` | 4 |
| 6 | `tool-calls.md` | For an agent, the reply is the least interesting output | — | `tool_calls_args` failure | 3.5 |
| 7 | `gates.md` | Gate on aggregates. And be honest about the statistics. | group + `must_pass` | group summary, exit override | 3.5 |
| 8 | `one-contract.md` | One contract. Three places to run it. | — | — | 2 |
| 9 | `agents-author-evals.md` | And then the agent writes the *evals* too | — | Claude Code authors YAML, green first try | 3 |
| 10 | `whats-in-the-box.md` | What else is in the box | — | voice (optional) | 1 |

**Cut levers, in order:** beat 1 → 2 min · beat 5's cast · beat 3 → 3 min · beat 10 folded
into the close. That reaches 25 minutes with the argument intact.

### Beats 2 and 3 — the fundamentals

Beat 2 carries no code, deliberately: a breather after the live demo. Four jobs a test does —
reproducible failure, non-recurring bugs, documentation that cannot drift, and the fourth that
pays for the other three: **licence to change code you no longer remember writing**. That
reframing is what connects to the talk's real question, which is not "does my agent work" but
"does it still work after I edited the prompt".

Beat 3 does the mechanics: a `test_` function, a bare `assert`, pytest's assertion rewriting
(`assert 100 == 90` reporting the call that produced the 100), fixtures, `parametrize`. Then
the four properties — deterministic, single-valued, exact, cheap — in that order, because
beat 4 knocks them down in the same order.

### Beats 3 and 4 — the visual rhyme

Beat 4's SVG **reuses beat 3's exact geometry**, broken: the single output becomes a
distribution, the assertion samples one point from it, and all four property labels are struck
through. This is load-bearing, not decorative. Two unrelated diagrams would not make
"all four break at once" legible; the rhyme makes it literal.

### Beats 5 and 6 — the tool-call handoff

An earlier draft named the tool evaluators in the tiers diagram *and* covered them a page
later, which read as duplication. The fix:

- Beat 5's tiers diagram names the **structural** tier and explicitly hands off
  (`▸ the whole of the next page`). It does not enumerate evaluators.
- Beat 6 opens by claiming that row, and gives the reason it sits beside the cheap
  deterministic tier rather than up with the judge: **a tool call is a string.** `ToolCall`
  subclasses `str`, so checking one costs what checking a substring costs. That fact is the
  connective tissue between the two pages.

Beat 6 is also where the talk's thesis lands: the failing run's *prose was flawless* and the
agent double-booked the customer, exactly as in beat 1.

### Beat 7 — the statistics

Two moves. Group thresholds and `must_pass` pins as the answer to "a probabilistic suite fails
somewhere every run, so don't let every red turn CI red". Then the honest caveat: this is not a
hypothesis test, it is a tripwire; the statistical power comes back at the group level, where a
gate over forty evals aggregates hundreds of runs.

## API surface to write against

`main` is mid-refactor. **Write every page against the PR #38 surface**
(`refac/type-safety-pydantic`), which the author states is close to final.

### The agent contract (beat 8's slide)

```python
async def agent(history: History) -> AgentReply
```

- `History = list[Message]`
- `Message` — frozen slotted dataclass with `role`, `content`, `audio`; also a `Mapping`, so
  `history[-1]["content"]` remains valid. Docs teach `.content`. `to_dict()` drops the
  plugin-internal `audio` key. `json.dumps` on a Message raises, by design.
- `AgentReply` — `NamedTuple(reply: str, tool_calls: ToolCalls)`, exported from
  `pytest_agent_eval`. Destructuring still works; returning a plain tuple is still valid.
- `ToolCalls = Sequence[str]` (not `list` — `list` is invariant).
- `ToolCall(str)` with `.args: ToolArgs | None` and `.name`. Name-based checks
  (`"book_slot" in ctx.tool_calls`) unchanged.
- `AgentCallable = Callable[[History], Awaitable[tuple[str, ToolCalls]]]` — the plain tuple, so
  both adapters and hand-written agents satisfy one alias.

Beat 8's argument makes the point that **naming the types did not narrow what the plugin
accepts** — every old form still works. That is the page's whole reason to exist.

### Unchanged, safe to write against now

`Turn`, `Expect(evaluators=[...])`, and all evaluator names — `ContainsEvaluator`,
`ToolCallEvaluator`, `ToolCallArgsEvaluator`, `ToolCallArgsJudgeEvaluator`, `JudgeEvaluator`.
YAML transcript fields, CLI flags, `pytest` terminal output, and the group-summary format are
all unchanged.

### New evidence for beat 9

Three PR #38 outcomes strengthen the didactic-errors argument and should be cited there:

1. `[tool.agent_eval]` is now **strictly validated** — `threshold = "high"` is rejected at
   load rather than failing later inside a score comparison.
2. The `INTERNALERROR` crash on a missing `llm_eval_agent` fixture is fixed, so the plugin's
   own didactic skip message finally appears in the situation it was written for.
3. `py.typed` now ships, so the types reach users' checkers.

## Assets

### Casts — 6 required, 1 insurance, 1 optional

All asciinema, all terminal, recorded at **90 columns** (a `.cast` cannot be reflowed later).

| Cast | Beat | Target |
|---|---|---|
| `beat-01-broken-agent.cast` (insurance) | 1 | 1:40 |
| `beat-03-pytest-basics.cast` | 3 | 0:50 |
| `beat-04-flake.cast` | 4 | 0:35 |
| `beat-05-threshold.cast` | 5 | 0:30 |
| `beat-06-toolcalls.cast` | 6 | 0:40 |
| `beat-07-groups.cast` | 7 | 0:25 |
| `beat-09-authoring.cast` | 9 | 0:45 |
| `beat-10-voice.cast` (optional) | 10 | 0:20 |

**`beat-04-flake.cast` is the one that has to be right.** Every other cast illustrates; that
one *is* the argument. It must not be rigged: pick a prompt where a naive
`assert "confirmed" in reply` genuinely fails about a third of the time because the model says
"you're all set" or "reserved" instead. Record real sessions and choose a good take.

### SVGs — 5

Beat 2 (commit timeline), beat 3 (four properties), beat 4 (the same, broken), beat 5 (three
tiers), beat 7 (group gate). Beat 1's trace diagram is optional and built only if time allows —
the live demo carries that beat.

Hand-authored inline SVG, geometric only. Theme-aware through CSS custom properties so a single
file works in both palettes; do not ship light/dark image pairs.

### Demo agent

One booking agent, used by every cast.

- Tools: `authenticate`, `fetch_availability`, `create_booking`, `update_booking`,
  `cancel_booking`.
- One **deliberately broken variant** for beat 1 that double-books.
- Pins `pytest-agent-eval==0.3.0` **from PyPI**, not the working tree, so a mid-flight refactor
  cannot break the talk demo.
- Lives **outside `examples/`**. CI already runs that directory (`1783c4d`), and the demo should
  be coupled to neither CI nor the refactor.

The domain is already the repo's convention — every existing example is booking-themed
(`booking_confirmation`, `create_booking`, `reschedule`, `gate:booking`), so the casts stay
consistent with the docs for free.

## Build order

Talk-first, per the decision above.

1. **Keyboard and instant-nav check.** Cheap, and it is the failure that ruins a live talk.
2. **Demo agent**, plus the broken variant. Blocks every cast.
3. **`beat-04-flake.cast`.**
4. Remaining casts.
5. **Five SVGs.** Load-bearing for the room too, not just the reader.
6. Zones 1–3 on all ten pages.
7. **Give the talk.**
8. Zone-4 prose.
9. Enable `navigation.tabs`, add Learn to nav.

**Beat 8 is written last regardless** — it is the page whose content the refactor can still
invalidate.

## Risks and open items

Everything here is stated as *needs verifying*. Zensical is a newer generator and its behaviour
should not be extrapolated from mkdocs-material.

### Verify before building

- Does zensical support `navigation.tabs`, and how does it treat a top-level page (Home) when
  tabs are on?
- Does zensical have a `not_in_nav` equivalent, so Learn pages can build and be reachable by
  direct URL without appearing in nav?
- Does the asciinema player survive `navigation.instant`? Instant nav swaps content without a
  full page load, so players on pages 2–10 likely will not initialise. This is the same family
  of problem as the Context7 widget (`eddd2ce`, `3749226`, which had to move to the scripts
  block). Mitigation: re-init on the nav event, or disable instant nav for Learn.
- **Do asciinema-player key bindings collide with the theme shortcuts?** `9c1627d` was a fix for
  widget keystrokes triggering theme shortcuts. The player binds space and arrows, and the
  collision would fire when pressing space to play a cast in front of the room. Check first.
- Does `async def agent(history: History) -> AgentReply` survive to PR #38 merge unchanged?

### Known constraints

- asciinema cannot record GUI, so the JSON Schema → editor autocomplete story on beat 9 must be
  prose, not a demo. The cast shows Claude Code writing the YAML and pytest going green, which
  is the stronger half.
- Present from a local build, not the deployed site.

## Out of scope

- Moving Getting started or Examples into Learn. Explicitly rejected: nothing moves.
- A separate slide toolchain (Marp, reveal.js). Explicitly rejected: the pages *are* the deck.
- Restructuring into three tabs (Learn / Guides / Reference). Better long-term IA, too large a
  change with a talk deadline live.
- Adding the demo agent to `examples/` and CI.
