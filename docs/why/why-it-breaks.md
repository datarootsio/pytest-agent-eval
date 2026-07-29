# All four break at once

<figure class="why-fig">
<div class="why-fig-scroll">
<svg viewBox="0 0 760 260" role="img" aria-label="The same pipeline as the previous page, broken: the single output has become a distribution of replies, the assertion samples one point from it, and all four properties are struck through">
  <rect x="8" y="34" width="118" height="52" rx="8" class="s-box"/>
  <text class="s-node" x="67" y="65" text-anchor="middle">prompt</text>
  <rect x="176" y="34" width="128" height="52" rx="8" class="s-box"/>
  <text class="s-node" x="240" y="65" text-anchor="middle">agent</text>

  <path class="s-arrow" d="M126 60 H176"/>
  <path class="s-arrow" d="M170 55 l6 5 l-6 5" fill="var(--md-default-fg-color--light)"/>
  <path class="s-arrow" d="M304 60 H348"/>
  <path class="s-arrow" d="M342 55 l6 5 l-6 5" fill="var(--md-default-fg-color--light)"/>

  <path d="M356 96 C 386 96, 392 22, 424 22 C 456 22, 466 96, 500 96" fill="var(--why-amber-soft)" stroke="var(--why-amber)" stroke-width="1.6"/>
  <line x1="356" y1="96" x2="500" y2="96" stroke="var(--md-default-fg-color--lighter)" stroke-width="1.2"/>
  <line x1="452" y1="18" x2="452" y2="102" stroke="var(--why-red)" stroke-width="1.4" stroke-dasharray="4 3"/>
  <text class="s-lbl" x="456" y="16" fill="var(--why-red)">pass / fail</text>
  <circle cx="404" cy="70" r="3" fill="var(--why-green)"/>
  <circle cx="420" cy="52" r="3" fill="var(--why-green)"/>
  <circle cx="434" cy="60" r="3" fill="var(--why-green)"/>
  <circle cx="414" cy="82" r="3" fill="var(--why-green)"/>
  <circle cx="444" cy="76" r="3" fill="var(--why-green)"/>
  <circle cx="428" cy="40" r="3" fill="var(--why-green)"/>
  <circle cx="466" cy="72" r="3" fill="var(--why-red)"/>
  <circle cx="478" cy="86" r="3" fill="var(--why-red)"/>
  <text class="s-lbl" x="356" y="114">distribution of replies</text>

  <path class="s-arrow" d="M478 86 C 505 86, 505 60, 528 60" stroke="var(--why-red)" stroke-dasharray="3 3"/>
  <rect x="530" y="34" width="112" height="52" rx="8" class="s-box" stroke="var(--why-red)"/>
  <text class="s-node" x="586" y="58" text-anchor="middle">assert</text>
  <text class="s-lbl" x="586" y="76" text-anchor="middle" fill="var(--why-red)">one sample</text>
  <path class="s-arrow" d="M642 60 H676"/>
  <rect x="676" y="40" width="76" height="18" rx="5" fill="var(--why-green-soft)" stroke="var(--why-green)" stroke-width="1.2"/>
  <text class="s-lbl" x="714" y="53" text-anchor="middle" fill="var(--why-green)">PASS</text>
  <rect x="676" y="64" width="76" height="18" rx="5" fill="var(--why-red-soft)" stroke="var(--why-red)" stroke-width="1.2"/>
  <text class="s-lbl" x="714" y="77" text-anchor="middle" fill="var(--why-red)">FAIL</text>
  <text class="s-lbl" x="752" y="98" text-anchor="end" fill="var(--why-amber)">…both, at random</text>

  <text class="s-lbl-strong" x="8" y="160" fill="var(--md-default-fg-color--light)">1 · deterministic</text>
  <line x1="8" y1="156" x2="118" y2="156" stroke="var(--why-red)" stroke-width="1.6"/>
  <text class="s-lbl" x="8" y="176">temperature, tools,</text>
  <text class="s-lbl" x="8" y="190">model updates</text>

  <text class="s-lbl-strong" x="196" y="160" fill="var(--md-default-fg-color--light)">2 · single-valued</text>
  <line x1="196" y1="156" x2="316" y2="156" stroke="var(--why-red)" stroke-width="1.6"/>
  <text class="s-lbl" x="196" y="176">"you're all set" is</text>
  <text class="s-lbl" x="196" y="190">also correct</text>

  <text class="s-lbl-strong" x="392" y="160" fill="var(--md-default-fg-color--light)">3 · exact</text>
  <line x1="392" y1="156" x2="452" y2="156" stroke="var(--why-red)" stroke-width="1.6"/>
  <text class="s-lbl" x="392" y="176">substring checks are</text>
  <text class="s-lbl" x="392" y="190">a proxy, not a spec</text>

  <text class="s-lbl-strong" x="580" y="160" fill="var(--md-default-fg-color--light)">4 · cheap</text>
  <line x1="580" y1="156" x2="640" y2="156" stroke="var(--why-red)" stroke-width="1.6"/>
  <text class="s-lbl" x="580" y="176">≈ 4 s · $0.02</text>
  <text class="s-lbl" x="580" y="190">× every run</text>

  <line class="s-rule" x1="8" y1="212" x2="752" y2="212"/>
  <text class="s-note" x="8" y="236">You are not asserting on an output. You are asserting on a property of a distribution — from one sample.</text>
</svg>
</div>
<figcaption>svg — the <a href="what-is-a-test.md">previous page's</a> geometry, broken. The rhyme is the point.</figcaption>
</figure>

Recording pending: `beat-04-flake.cast` — target 0:35, 90 cols, the one that has to be right.

```console
$ for i in 1 2 3 4 5; do pytest -q tests/test_naive.py; done

.                                                          [100%]  1 passed
F                                                          [100%]  1 failed
    assert "confirmed" in reply
E   assert 'confirmed' in "You're all set for tomorrow at 10am — ref BK-4417."
.                                                          [100%]  1 passed
.                                                          [100%]  1 passed
F                                                          [100%]  1 failed
E   assert 'confirmed' in "Done! Your 10am slot is reserved."

# same code. same prompt. same commit.
```

## The argument

Run the naive test five times and it fails twice — not because the agent misbehaved, but because
"you're all set" and "reserved" are perfectly good confirmations that happen not to contain the
word we picked. Every one of the four properties is gone at once, and they took the binary
outcome down with them.

This part should feel familiar if you work with models: **you are looking at a sample, not the
distribution.** A single run cannot answer a question about a distribution's behaviour, and no
amount of staring at that one run will fix it.

The fourth property is the cruel one. The obvious remedy — run it many more times — is exactly
what costs seconds and cents per call, so you cannot buy your way out on every push.

## Go deeper

- [Evaluators](../evaluators.md) — what to assert instead of a hand-picked substring
- [Configuration](../configuration.md) — `runs`, `retries`, `timeout`
