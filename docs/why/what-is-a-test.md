# The anatomy of a test (in Pytest)

Imagine you have in your project:

```python
# In a `tests/test_pricing.py` file

def discount(subtotal: int, code: str) -> float:
    if code == "SPRING":
        return subtotal * 0.9
    return subtotal

def test_discount_applies_to_subtotal():
    assert discount(subtotal=100, code="SPRING") == 90

def test_discount_dont_apply_to_subtotal():
    assert discount(subtotal=100, code="SPRINGS") == 90
```

The `discount` function is tested in the `test_discount_applies_to_subtotal` and `test_discount_dont_apply_to_subtotal`, and we can verify with Pytest running:

<figure class="why-cast">
<div class="why-cast-mount"
     data-cast-id="ozZGIEKSEcn1FU8Q"
     data-cast-slug="01-pytest-basics"
     data-cast-poster="npt:0:02"
     role="img"
     aria-label="Two pytest runs on the same file. The first node id passes with a single dot. The second fails, and the assertion-rewrite traceback names test_discount_dont_apply_to_subtotal and reports assert 100 == 90 with the call that produced the 100."></div>
<figcaption>asciinema: <code>pytest -q</code> on a passing test, then on a failing one</figcaption>
</figure>

Simple pattern, but in complex codebases, where functions call functions, abstractions, dependencies and classes, having these guarantees increases the **confidence** that the existing code works as expected.

<figure class="why-fig">
<div class="why-fig-scroll">
<svg viewBox="0 0 760 240" role="img" aria-label="A test pipeline: fixed input, code under test, one output, an exact equality assertion, and a binary pass or fail, annotated with four properties: deterministic, single-valued, exact, and cheap">
  <rect x="8" y="34" width="118" height="52" rx="8" class="s-box"/>
  <text class="s-node" x="67" y="65" text-anchor="middle">input</text>
  <rect x="176" y="34" width="128" height="52" rx="8" class="s-box"/>
  <text class="s-node" x="240" y="65" text-anchor="middle">code</text>
  <rect x="354" y="34" width="118" height="52" rx="8" class="s-box"/>
  <text class="s-node" x="413" y="65" text-anchor="middle">output</text>
  <rect x="522" y="34" width="118" height="52" rx="8" class="s-box"/>
  <text class="s-node" x="581" y="65" text-anchor="middle">assert ==</text>

  <path class="s-arrow" d="M126 60 H176"/>
  <path class="s-arrow" d="M170 55 l6 5 l-6 5" fill="var(--md-default-fg-color--light)"/>
  <path class="s-arrow" d="M304 60 H354"/>
  <path class="s-arrow" d="M348 55 l6 5 l-6 5" fill="var(--md-default-fg-color--light)"/>
  <path class="s-arrow" d="M472 60 H522"/>
  <path class="s-arrow" d="M516 55 l6 5 l-6 5" fill="var(--md-default-fg-color--light)"/>
  <path class="s-arrow" d="M640 60 H676"/>

  <rect x="676" y="40" width="76" height="18" rx="5" fill="var(--why-green-soft)" stroke="var(--why-green)" stroke-width="1.2"/>
  <text class="s-lbl" x="714" y="53" text-anchor="middle" fill="var(--why-green)">PASS</text>
  <rect x="676" y="64" width="76" height="18" rx="5" fill="var(--md-code-bg-color)" stroke="var(--md-default-fg-color--lighter)" stroke-width="1.2"/>
  <text class="s-lbl" x="714" y="77" text-anchor="middle">FAIL</text>

  <path class="s-brace" d="M12 100 v8 h110 v-8"/>
  <text class="s-lbl-strong" x="16" y="128">1 · deterministic</text>
  <text class="s-lbl" x="16" y="144">same input,</text>
  <text class="s-lbl" x="16" y="158">every time</text>

  <path class="s-brace" d="M358 100 v8 h110 v-8"/>
  <text class="s-lbl-strong" x="358" y="128">2 · single-valued</text>
  <text class="s-lbl" x="358" y="144">exactly one</text>
  <text class="s-lbl" x="358" y="158">right answer</text>

  <path class="s-brace" d="M526 100 v8 h110 v-8"/>
  <text class="s-lbl-strong" x="526" y="128">3 · exact</text>
  <text class="s-lbl" x="526" y="144">equality, not</text>
  <text class="s-lbl" x="526" y="158">judgement</text>

  <path class="s-brace" d="M680 100 v8 h68 v-8"/>
  <text class="s-lbl-strong" x="620" y="186">4 · cheap</text>
  <text class="s-lbl" x="620" y="202">≈ 2 ms · $0</text>
  <text class="s-lbl" x="620" y="216">run it on every push</text>

  <text class="s-note" x="8" y="200">Four properties. Every one of them is load-bearing.</text>
  <line class="s-rule" x1="8" y1="228" x2="752" y2="228"/>
</svg>
</div>
<figcaption>svg: the four properties, redrawn broken on the <a href="why-it-breaks.md">next page</a></figcaption>
</figure>

## What is a test?

Mechanically, a pytest test is a function whose name starts with `test_` containing a bare
`assert`. There is no class to subclass and no assertion API to learn: pytest rewrites the
`assert` so a failure reports the actual values, which is why `assert 100 == 90` comes back with
the call that produced the 100. To run the same body over many inputs, `@pytest.mark.parametrize` takes the cases as data.

Conceptually it is a bet that four things hold. The input is **deterministic**. The output is
**single-valued**: one right answer to compare against. The assertion is **exact**, equality or
membership rather than taste. And the whole thing is **cheap**: milliseconds, no marginal cost,
which is the only reason it is sane to run thousands on every commit.

Those four are what let a test collapse into one bit and gate a merge. Hold them in that order. But what happens when we don't know exactly what the code will output?

## Go deeper

- [Python API](../python-api.md): `Turn`, `Expect`, and `parametrize` over transcripts
- [Configuration](../configuration.md): where eval settings live in `pyproject.toml`
- [pytest, fixtures](https://docs.pytest.org/en/stable/how-to/fixtures.html): the mechanism the agent fixture uses
