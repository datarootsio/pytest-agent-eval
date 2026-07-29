# Tests aren't about correctness. They're about *change*.

<figure class="why-fig">
<div class="why-fig-scroll">
<svg viewBox="0 0 760 234" role="img" aria-label="A commit timeline where a refactor introduces a regression and pytest fails at the commit that caused it, annotated with the four jobs a test does: reproducible, regression-proof, documentation, and licence to change">
  <text class="s-lbl" x="24" y="14">MAIN</text>
  <line x1="24" y1="64" x2="672" y2="64" stroke="var(--md-default-fg-color--lighter)" stroke-width="2"/>
  <rect x="192" y="28" width="290" height="20" rx="10" fill="var(--why-accent-soft)" stroke="var(--why-accent)" stroke-width="1.2"/>
  <text class="s-lbl" x="204" y="42" fill="var(--why-accent)">refactor: swap the booking backend</text>

  <circle cx="24" cy="64" r="5" fill="var(--why-green)"/>
  <circle cx="116" cy="64" r="5" fill="var(--why-green)"/>
  <circle cx="208" cy="64" r="5" fill="var(--why-green)"/>
  <circle cx="300" cy="64" r="5" fill="var(--why-green)"/>
  <circle cx="392" cy="64" r="5" fill="var(--why-green)"/>
  <circle cx="484" cy="64" r="6" fill="var(--why-red)"/>
  <circle cx="576" cy="64" r="5" fill="var(--md-default-fg-color--lighter)"/>
  <circle cx="668" cy="64" r="5" fill="var(--md-default-fg-color--lighter)"/>

  <path class="s-arrow" d="M484 76 V96" stroke="var(--why-red)"/>
  <text class="s-lbl-strong" x="470" y="112" fill="var(--why-red)">pytest fails here</text>
  <text class="s-lbl" x="470" y="128">4 minutes after the cause —</text>
  <text class="s-lbl" x="470" y="142">not 4 weeks, in production</text>

  <line class="s-rule" x1="24" y1="156" x2="736" y2="156"/>

  <text class="s-lbl-strong" x="24" y="176">reproducible</text>
  <text class="s-lbl" x="24" y="192">the same failure,</text>
  <text class="s-lbl" x="24" y="206">on demand</text>

  <text class="s-lbl-strong" x="184" y="176">regression-proof</text>
  <text class="s-lbl" x="184" y="192">yesterday's bug</text>
  <text class="s-lbl" x="184" y="206">cannot come back</text>

  <text class="s-lbl-strong" x="356" y="176">documentation</text>
  <text class="s-lbl" x="356" y="192">the only spec that</text>
  <text class="s-lbl" x="356" y="206">cannot go stale</text>

  <text class="s-lbl-strong" x="536" y="176" fill="var(--why-amber)">licence to change</text>
  <text class="s-lbl" x="536" y="192" fill="var(--why-amber)">the reason the other</text>
  <text class="s-lbl" x="536" y="206" fill="var(--why-amber)">three matter at all</text>
</svg>
</div>
<figcaption>svg — the four jobs a test does</figcaption>
</figure>

## The argument

Ask why people write tests and you get four answers. Tests make a failure **reproducible**, so
you can look at it whenever you like instead of waiting for it to happen again. They make bugs
**non-recurring** — the fix comes with a guard, so yesterday's incident cannot be reintroduced
next quarter by someone who never heard about it. They are **documentation** that cannot drift,
because a lie in a test suite fails loudly.

The fourth is the one that actually pays for the other three: a test suite is what lets you
**change code you no longer remember writing**. Rename the function, swap the backend, upgrade
the dependency — the suite tells you within minutes whether you got away with it.

That framing matters here, because "my agent works" is not the interesting question. "My agent
still works, after I edited the prompt" is.

## Go deeper

- [Getting started](../getting-started.md) — where the same argument turns into a first eval
- [pytest — get started](https://docs.pytest.org/en/stable/getting-started.html) — the framework this plugin extends
