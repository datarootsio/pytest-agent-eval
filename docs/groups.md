# Group thresholds

LLM evals are probabilistic; a suite of them fails somewhere almost every run. Group thresholds let you gate CI on **aggregate pass rates** ("90% of booking evals must pass") instead of every individual test, while still pinning down the tests that must never break.

## Configuration

Groups live under `[tool.agent_eval.groups]` in `pyproject.toml`:

```toml
[tool.agent_eval.groups.booking]
threshold = 0.9                          # 90% of matched tests must pass
tags = ["gate:booking"]                  # match transcripts by tag
pytest_markers = ["booking"]             # ...and/or plain tests by marker
must_pass = ["booking_confirmation"]     # these must individually pass

[tool.agent_eval.groups.smoke]
tags = ["smoke"]                         # threshold defaults to 1.0
```

| Key              | Type        | Default | Description                                                        |
|------------------|-------------|---------|--------------------------------------------------------------------|
| `threshold`      | `float`     | `1.0`   | Fraction of matched, non-skipped tests that must pass (0.0-1.0)    |
| `tags`           | `list[str]` | `[]`    | Transcript tags that select members                                |
| `pytest_markers` | `list[str]` | `[]`    | Pytest marker names that select members                            |
| `must_pass`      | `list[str]` | `[]`    | Test identities that must individually pass whenever they run      |

Group config is validated strictly: unknown keys, bad types, and out-of-range thresholds abort the run with a usage error. A typo'd `must_pass` silently disabling a CI gate would be worse.

Markers named in `pytest_markers` are auto-registered, so `--strict-markers` projects don't need extra `markers =` ini entries.

## Membership

A test belongs to a group when **any** of its tags or markers intersects the group's `tags`/`pytest_markers`:

- YAML transcripts contribute their `tags:` list (also visible as `tags=` on their `agent_eval` marker).
- Python tests contribute their pytest markers, so `@pytest.mark.booking` joins any group with `pytest_markers = ["booking"]` — plain non-LLM tests included.

A test can belong to several groups; it counts in each.

## `must_pass` semantics

`must_pass` entries are **assertions, not selectors** — they don't add tests to the group. An entry matches a test whose identity equals it exactly or is one of its parametrizations (`test_thing` matches `test_thing[case1]`). Identities are the transcript `id` for YAML tests and the test name for Python tests.

- If any matching test **failed**, the group fails regardless of its pass rate.
- If no matching test ran (deselected or skipped), the summary prints a warning — partial selection shouldn't flip gates.

## Pass/fail semantics

For each group per session:

- **Denominator** = matched tests that ran. Skipped tests are excluded (so are xfails, which pytest reports as skips). A group whose matches were all skipped renders as `SKIPPED`, never as a vacuous pass.
- The group **passes** when `passed / total >= threshold` and no `must_pass` entry failed.
- A group that matches nothing prints a `WARNING` — usually a stale tag.

Under partial selection (`pytest -k booking_smoke`), the denominator is what actually ran, and a note flags the deselection. In CI you'll normally run the full suite, where the distinction vanishes.

## Exit-code override

When tests failed but every gate is green, the exit code is overridden to `0`. The override applies **only** when all of these hold:

- at least one group matched tests that ran,
- every such group met its threshold (including `must_pass`),
- **every failed test in the session belongs to a gated group** — a failing plain unit test or an ungrouped transcript keeps CI red,
- there were no collection errors.

!!! note "The stats bar still shows failures"
    An absorbed failure is still a failure in pytest's own summary (`1 failed, 3 passed`) — only the exit code changes, and the group summary prints `exit code overridden to 0` so logs stay honest.

## Terminal output

```text
============================== group summary ===============================
booking: 9/10 passed (90%) >= 90% required -- PASSED
  failures: booking_edge_case
  must_pass: booking_confirmation ok
smoke: 4/4 passed (100%) >= 100% required -- PASSED
exit code overridden to 0: all group thresholds met
```

Failures are always listed when present — even inside a passing group — so absorbed regressions stay visible in logs.

The [markdown report](reporting.md) gains a `## Groups` section with the same numbers when groups are configured.

## Parallel execution

Group aggregation works under `pytest-xdist` (`-n auto`): workers forward each test's identity, tags, and markers to the controller, which aggregates and applies the override exactly as in single-process runs.
