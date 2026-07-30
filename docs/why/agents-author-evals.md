# LLM friendly 🤗

AI-native development is the new norm. And `pytest-agent-eval` is also designed to pair nicely with AI coding agents.

<figure class="why-cast">
<div class="why-cast-mount"
     data-cast-id=""
     data-cast-slug="07-agent-authors-eval"
     data-cast-poster="npt:0:02"
     role="img"
     aria-label="A coding agent is asked to write an eval for the reschedule flow. It reads the published schema, writes a YAML transcript to tests/evals, and the eval passes on the first pytest run with no edits."></div>
<figcaption>asciinema: a real Claude Code session writing a YAML transcript</figcaption>
</figure>

??? note "What the recording shows"

    A live coding session runs for minutes and no two takes print the same words, so there
    is no transcript to paste here. What the recording shows:

    - A scratch project with four things in it: a `pyproject.toml` naming
      `yaml_dirs`, a `conftest.py` whose `llm_eval_agent` fixture is a stub with two fixed
      replies, the `AGENTS.md` snippet this documentation publishes, and an empty
      `tests/evals/`.
    - One prompt, typed at Claude Code's `>` box: `write an eval for the reschedule flow.`
    - The agent reads `AGENTS.md` and `conftest.py`, fetches the published `llms.txt` and
      JSON Schema, and writes `tests/evals/reschedule.yaml` — as Claude Code's own tool
      lines and their results, not as narration.
    - Back at the shell: `cat tests/evals/reschedule.yaml`, then
      `pytest --agent-eval-live -q`. One dot, one pass, first try, no edits.

    The stub fixture and the `AGENTS.md` snippet are part of the setup and they are doing
    real work: the model writes expectations that hold because it can read the replies it
    is writing them against. There is no API key anywhere in the session.

## The YAML transcript surface

We also allow for tests and conversations and cases to be expressed as YAML files, which is more visually appealing for humans but also more LLM-friendly:

```yaml
# tests/evals/reschedule.yaml
# yaml-language-server: $schema=https://datarootsio.github.io/pytest-agent-eval/schema/transcript.json

id: reschedule_flow          # becomes the pytest test name
threshold: 0.8               # fraction of runs that must pass
runs: 3                      # how many times to replay the whole transcript
tags: [gate:booking]         # what the group gates match on

turns:
  - user: "Book me a slot tomorrow at 10am."
    expect:
      reply_contains_any: ["confirmed", "booked"]     # deterministic
      tool_calls_include: [create_booking]            # structural
      tool_calls_args:
        - tool: create_booking
          args: {time: "10am"}                        # subset by default
          mode: subset                                # or exact

  - user: "Actually make it 11am."
    expect:
      tool_calls_include: [update_booking]
      tool_calls_exclude: [create_booking]
      reply_matches_any: ['BK-\d+']                   # regex, quoted so \d survives
      judge:                                          # semantic, only where it is needed
        rubric: >
          The reply must state the new time and repeat the existing booking
          reference unchanged. It must not ask the user to repeat anything.
```

There is no Python in that file and no Python file beside it. The plugin collects any `*.yaml`
under `yaml_dirs` and generates one pytest test per transcript *dynamically*, named by its `id`:

```toml
# pyproject.toml

[tool.agent_eval]
yaml_dirs = ["tests/evals"]
```

<figure class="why-cast">
<div class="why-cast-mount"
     data-cast-id="XcNHiQW5xzH4eHNb"
     data-cast-slug="08-collect-only"
     data-cast-poster="npt:0:02"
     role="img"
     aria-label="pytest collects a YAML transcript as a test node id with no Python file beside it, then reports that the eval was skipped because live mode is off."></div>
<figcaption>asciinema: <code>pytest --collect-only -q</code> on a YAML transcript</figcaption>
</figure>

??? note "Transcript"

    ```console
    $ pytest --collect-only -q
    tests/evals/reschedule.yaml::reschedule_flow

    1 eval test(s) skipped: live mode is off. Pass --agent-eval-live or set EVAL_LIVE=1.
    1 test collected in 0.00s
    ```

Which means a transcript is a first-class pytest test from there on. `-k reschedule` selects it,
`-n auto` distributes it, a tag puts it behind a gate, and the one thing it needs from you is the
`llm_eval_agent` fixture that says what to run it against.

## Two audiences, one file

Generating tests from data rather than from code is what makes both readers happy at once, and they
want different things.

**A human reviewing cases** gets a diff about the case. A transcript reads top to bottom like the
conversation it describes, so adding coverage is adding a file and tightening an expectation is a
one-line change. Nobody has to read around imports, fixtures and an async call graph to see which
behaviour is being pinned, which means review comments land on the assertion instead of the
plumbing. A product person can read it, and argue with it, without reading Python.

**A model writing cases** gets the format it is most reliable at. Markup is a fixed set of keys
with a published schema, so there is one shape to hit and `additionalProperties: false` rejects
anything else at load. Ask for Python instead and the model has to get imports, `async`, fixture
names and a call graph right, any of which can be subtly wrong while still executing. Here the
worst case is a field name, and a field name is exactly what the loader can catch and correct.

`pytest-agent-eval` was also designed with AI-native coding in mind. We also include other
LLM-friendly features to support agent-driven development:

`schema`

:   **a published JSON Schema** with `additionalProperties: false`, so invalid files fail loudly, not silently

`errors`

:   **didactic by design**: `unknown field 'tool_call_include'. Did you mean 'tool_calls_include'?`, with the schema URL attached

`config`

:   **`[tool.agent_eval]` is strictly validated**: `threshold = "high"` is rejected at load, not deep inside a score comparison

`fixtures`

:   **the missing-fixture case is a message, not a crash**: it tells you which fixture and where to put it

`types`

:   **`py.typed` ships**, so the named contract reaches the agent's type checker too

`context`

:   **`llms.txt` and `llms-full.txt`** at the site root, plus an `AGENTS.md` snippet to paste

`LLM docs`

:   Documentation available via [`context7`](https://context7.com)

`examples`

:   **runnable projects CI keeps green**: copied code starts from a known-good state

## Go deeper

- [Using with coding agents](../agents.md): the `AGENTS.md` snippet and schema-first authoring
- [YAML API](../yaml-api.md): every transcript field the schema validates
- [Examples](../examples.md): the runnable projects CI keeps green
