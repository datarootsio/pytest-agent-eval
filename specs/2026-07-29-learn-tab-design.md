# "Why pytest-agent-eval" tab

**Status:** pages, nav, and styles shipped. Every cast is a placeholder; the demo agent, the
recordings, and the asciinema player are not built.
**Date:** 2026-07-29
**Visual reference:** <https://claude.ai/code/artifact/21018351-8c7d-464d-b251-5d74bcee339f>

## Summary

Add a second top-level tab to the docs site — **Why pytest-agent-eval**, alongside **Docs** —
containing a ten-page narrative that argues why agent evals are necessary and how this package
answers that. The same pages are the source for a 20–30 minute conference talk.

The tab label is plain text, no backticks: nav titles come from TOML and render through
`{{ ref.title or nav_item.title }}` with Jinja autoescaping
(`zensical/templates/partials/nav-item.html:15`), so backticks would appear literally.

The docs have no "why" content today: `docs/index.md` goes from tagline to `pip install` in
three lines, and there are no visuals anywhere in the site. The talk assets (five diagrams,
eight terminal recordings) are the thing the docs are missing regardless of whether the talk
is ever given again. That is the justification for the effort.

## Decisions

These are settled. Each is recorded with the reason, because the reasons constrain
implementation.

| Decision | Reason |
|---|---|
| A separate **Why pytest-agent-eval** tab, FastAPI/SQLModel style | The narrative is read in order; reference docs are not. Mixing them makes both worse. |
| **Nothing moves.** Docs tab keeps its exact current nav | Zero broken links, no muscle-memory reset. The last page links across to Getting started. |
| Pages **must stand alone** for a reader without the speaker | The section is a permanent docs asset, not talk scaffolding. |
| **No present/read mode switch** | One register. ~~Claims are sized to work read at a desk *and* projected~~ — the sizing was later dropped, so the register is the docs' own; the speaker scrolls past the prose. |
| Beat 1 is a **live screen share in a separate window**, not a page cast | It is the opener and it needs to be live. An asciinema insurance take exists as a fallback. |
| **All** screen recordings are asciinema | Rules out GUI demos — notably editor autocomplete from the JSON Schema, which becomes prose. |
| **One purpose-built booking agent** for every cast | Continuity. The room learns one domain in beat 1 and never re-learns it. |
| Talk-first build order; zone-4 prose backfilled after | The date is near. See [Build order](#build-order). |
| ~~Joins the published nav only when prose lands~~ — **dropped** | Not implementable. `tests/test_docs_surface.py:35` asserts `pages == nav` exactly and zensical has no `not_in_nav` equivalent, so an unlisted page cannot ship. The prose was written up front instead, which the stand-alone requirement wanted anyway. |
| The section is **excluded from `llms-full.txt`** | It is narrative argument for human readers and carries no API facts an agent needs. Mirrors the existing `api-reference/` filter. |

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

Enabling tabs is **not** an additive change. Tabs *are* the top-level nav entries, so turning
them on required nesting the seven existing top-level entries under a new `Docs` parent. No page
moved and no URL changed; the Docs sidebar simply gained a grouping level. The assignment is:

- **Docs** — Home, Getting started, Examples, Writing evals, Running & CI, Using with coding
  agents, API reference. Unchanged in content and order.
- **Why pytest-agent-eval** — the ten narrative pages, in `docs/why/`, served at `/why/<page>/`.

Tab bar order is **Docs, Why pytest-agent-eval**. `docs/index.md` stays the site root and stays
under Docs.

Every nav entry must be a `{ title = path }` table. A bare-string entry — the mkdocs idiom for a
`navigation.indexes` section landing page — breaks tooling: both `_walk_nav` in
`scripts/build_llms_full.py` and the walker in `tests/test_docs_surface.py:18` call
`entry.values()`. `why/index.md` is therefore a titled page inside the section rather than the
section's own index; the tab still lands on it.

### Confirmed zensical capabilities

Checked against zensical 0.0.51 rather than extrapolated from mkdocs-material:

- `navigation.tabs` and `navigation.tabs.sticky` are supported
  (`templates/partials/header.html:5,64-66`, `nav.html:6`, `base.html:156-157`) and compose with
  the existing `navigation.sections`. Tabs render above 1220px and collapse into the drawer below
  it — widen the window before concluding they are broken.
- `extra_css` is supported (`templates/base.html:82`), path relative to `docs_dir`.
- The palette scheme attribute is set on `<body>` (`templates/base.html:100`), so dark overrides
  are `body[data-md-color-scheme="slate"]`.
- Relative `.md` links are rewritten **even inside raw HTML blocks**, so a link in a raw
  `<figcaption>` resolves like any other.
- `md_in_html` and `pymdownx.superfences` compose: a fenced block inside a
  `<div markdown="1">` highlights normally. This was the one build-time unknown.
- There is **no `not_in_nav` equivalent.**

## Page anatomy

Every page has the same five zones, top to bottom. The order is the design: a reader
gets the argument, a presenter stays in zones 1–3.

1. **Claim** — one room-legible line. ~~`clamp()`-sized so it reads at a desk and projects.~~
   **Not implemented** — a plain H1 at the theme's own scale.
2. **One SVG** — carries exactly one idea. Theme-aware via CSS custom properties.
3. **One cast** — asciinema, 20–50s, one idea.
4. **Argument** — 120–180 words that make the point unaided. ~~Set in a serif to separate it
   from the slide-shaped zones above.~~ **Not implemented** — body text like any other page.
5. **Go deeper** — two or three links into the Docs tab.

The two struck clauses were dropped on the instruction that nothing in this section is styled
differently from the rest of the docs. See
[How the zones are realised in markdown](#how-the-zones-are-realised-in-markdown) for what that
costs a presenter.

Zones 2 and 3 are both optional per page; zones 1, 4 and 5 are mandatory.

**Presenting discipline:** never read zone 4 aloud. That is what blows the clock.

### How the zones are realised in markdown

**No custom typography.** The mock's type treatment — the `clamp()`-scaled claim, the amber
emphasis inside it, the mono captions and meta lines, the small-caps section headings, the serif
argument prose — is **not** implemented. Every piece of text on these pages takes the theme's own
font, size and colour, exactly like the rest of the docs. The claim is a plain H1; it is
room-legible because it is short, not because it is scaled.

- Zone 1 is a plain H1. Nothing else.
- Zone 2 is **inline** SVG in a raw `<figure class="why-fig">`, never an `.svg` file in an `<img>`:
  an external file cannot inherit the page's CSS custom properties, so it could not be theme-aware
  without shipping light/dark pairs. No `markdown="1"` on these — the figure is passed through as
  raw HTML. The figcaption is styled by the theme.
- Zone 3 is a plain sentence naming the pending recording, followed by an ordinary fenced `console`
  block. No wrapper, no marker styling. The intended terminal output is useful documentation on its
  own, so it ships as real text that a future asciinema player can wrap rather than as a stub, and
  it gets the theme's normal code styling including the copy button.
- Zones 4 and 5 are plain `## The argument` and `## Go deeper`.
- Content the mock carried beyond the five zones — the agent signature, the tool-call assertion
  list, the "Monday morning" commands — uses already-enabled extensions (`def_list`,
  `admonition`, fenced blocks) rather than new bespoke components.

This drops two things the design asked for, deliberately: zone 1's `clamp()` sizing and zone 4's
serif register. **A presenter therefore cannot project these pages as-is** — the claim will not
read from the back of a room at body-text scale. If the talk needs that, it wants a present-mode
stylesheet, which is a separate decision from the docs asset.

### Colour

`docs/stylesheets/why.css` is diagram support only. It does two things the theme cannot: keep a
wide diagram's scrollbar off the page body (`.why-fig-scroll { overflow-x: auto }`), and give
inline SVG the fills and font stacks it does not inherit from the typeset styles. Those SVG rules
mirror the docs' own variables — `--md-default-fg-color` and its `--light`/`--lighter` steps,
`--md-code-bg-color`, `--md-code-font-family`, `--md-text-font-family` — rather than introducing
values of their own. The font sizes in them are diagram geometry, not a typographic choice.

Only four semantic colours are defined — green, red, amber, accent — with slate overrides; their
`-soft` fills are `color-mix`ed against `--md-default-bg-color`, so one declaration covers both
schemes.

Amber marks the threshold zone consistently inside the diagrams: `score=0.67 >= 0.66`, the
distribution envelope, the semantic tier, the exit-code override.

The semantic values are **not** the mock's. The diagrams label 11–13px text directly on those
soft tints, and the mock's light-mode green (3.77:1) and amber (3.29:1) failed WCAG AA there, as
did `--md-typeset-a-color` as the accent (3.05:1). The shipped set clears 4.5:1 against both the
page background and its own tint in both schemes. `--md-primary-fg-color` (#4051b5) is fine as the
default-scheme accent but must not be carried into slate, where it stays #4051b5 on near-black.

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

**Superseded during implementation.** This section planned to write against the PR #38 surface
(`refac/type-safety-pydantic`). That PR is not merged, so `AgentReply`, `History`, `Message`, and
`ToolCalls` do not exist in the tree the docs are built from — and a published page cannot describe
types that do not ship. Beat 8 was written against the shipped contract instead:

```python
async def agent(messages: list[dict]) -> tuple[str, list[str]]
```

which is what `docs/adapters.md:236-241` already documents. `ToolCall(str)` with `.args` *does*
ship and is exported, so beats 6 and 8 keep the "a tool call is a string" argument unchanged.

Beat 8's point survives the substitution intact — arguably better grounded. Instead of "naming the
types did not narrow what the plugin accepts", it now argues that this is the loosest contract that
still supports every assertion in the narrative: bare names get the name checks, `ToolCall(name,
args)` lights up the argument checks on the same suite, because a `ToolCall` *is* a `str`. **Richer
assertions never demanded a richer contract.**

**When PR #38 merges, rewrite `docs/why/one-contract.md` first** — it is the only page coupled to
the refactor.

Two other claims drafted in the mock for beat 9 were dropped for the same reason: strict
`[tool.agent_eval]` validation (`config.py` does not validate) and `py.typed` (absent). The claims
that survive are all verified against the tree: the JSON Schema with `additionalProperties: false`,
the `Did you mean ...?` unknown-field hint (`yaml_loader.py:56-61`), and the didactic
missing-fixture message (`yaml_loader.py:326-333`).

### The PR #38 contract, for when it lands

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

Beat 8's argument would make the point that **naming the types did not narrow what the plugin
accepts** — every old form still works.

### Unchanged, safe to write against now

`Turn`, `Expect(evaluators=[...])`, and all evaluator names — `ContainsEvaluator`,
`ToolCallEvaluator`, `ToolCallArgsEvaluator`, `ToolCallArgsJudgeEvaluator`, `JudgeEvaluator`.
YAML transcript fields, CLI flags, `pytest` terminal output, and the group-summary format are
all unchanged.

### New evidence for beat 9, when PR #38 lands

Three PR #38 outcomes strengthen the didactic-errors argument and should be added there on merge.
None of the three is true in the tree today, so none is claimed on the page yet:

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

**All eight are placeholders today.** Each ships as a fenced `console` block holding the intended
output, preceded by a plain sentence naming the file and its target duration. Recording one is a
matter of replacing the fence, not of adding a page.

### SVGs — 6 shipped

Beat 2 (commit timeline), beat 3 (four properties), beat 4 (the same, broken), beat 5 (three
tiers), beat 7 (group gate). Beat 1's trace diagram was optional on the grounds that the live
demo carries that beat — it shipped anyway, because a *reader* gets no live demo and the opening
claim needs something concrete.

Beat 4 reuses beat 3's exact geometry, broken. See [the visual rhyme](#beats-3-and-4-the-visual-rhyme).

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

The original order was talk-first, with nav last. It was reordered because the "join nav later"
phasing turned out not to be implementable (see [Decisions](#decisions)) — the docs part shipped
first instead, complete enough to stand on its own.

**Done:**

1. Enable `navigation.tabs`, nest the existing nav under `Docs`, add the second tab.
2. All ten pages: zones 1–5, including the zone-4 prose, and six SVGs.
3. Cast placeholders holding the intended output.
4. `docs/stylesheets/why.css`; exclude `why/` from `llms-full.txt`; mirror the exclusion in
   `tests/test_docs_surface.py`.

**Remaining, in order:**

5. **Keyboard and instant-nav check.** Cheap, and it is the failure that ruins a live talk.
6. **Demo agent**, plus the broken variant. Blocks every cast.
7. **`beat-04-flake.cast`.**
8. Remaining casts, replacing the placeholder fences.
9. **Give the talk.**

**Rewrite beat 8 when PR #38 merges** — it is the only page the refactor can invalidate.

## Risks and open items

### Verified during implementation

Recorded in [Confirmed zensical capabilities](#confirmed-zensical-capabilities). In summary:
`navigation.tabs` and `extra_css` are supported; `md_in_html` composes with `superfences`; there
is **no `not_in_nav` equivalent**, which forced the nav decision above; and a top-level page under
a tab keeps its URL, so nothing broke.

`pytest tests/test_docs_surface.py` is the gate that proves it — nav, on-disk pages, `llms.txt`
links, and the `llms-full.txt` build all stay in sync, and the new pages are covered
automatically.

### Still open

- Does the asciinema player survive `navigation.instant`? Instant nav swaps content without a
  full page load, so players on pages 2–10 likely will not initialise. This is the same family
  of problem as the Context7 widget (`eddd2ce`, `3749226`, which had to move to the scripts
  block). Mitigation: re-init on the nav event, or disable instant nav for this section.
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

- Moving Getting started or Examples into the new tab. Explicitly rejected: nothing moves.
- A separate slide toolchain (Marp, reveal.js). Explicitly rejected: the pages *are* the deck.
- Restructuring into three tabs (Learn / Guides / Reference). Better long-term IA, too large a
  change with a talk deadline live.
- Adding the demo agent to `examples/` and CI.
