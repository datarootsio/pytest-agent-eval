# LLM friendly 🤗

AI-native development is the new norm. And `pytest-agent-eval` is also designed to pair nicely with AI coding agents.

```console
$ claude
> write an eval for the reschedule flow.

  …reading llms.txt
  …creating tests/evals/reschedule.yaml

  # yaml-language-server: $schema=.../schema/transcript.json
  id: reschedule_flow
  threshold: 0.8
  runs: 3
  tags: [gate:booking]
  turns:
    - user: "Actually make it 11am."
      expect:
        tool_calls_include: [update_booking]
        tool_calls_exclude: [create_booking]

$ pytest --agent-eval-live -q
.                                                          [100%]
1 passed in 9.7s          # first try, no edits
```

## The YAML transcript surface

We also allow for tests and conversations and cases to be expressed as YAML files, which is more visualy appealing for humans but also more LLM-friendly:

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

```console
$ pytest --collect-only -q
evals/reschedule.yaml::reschedule_flow

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

`Pytest-agent-eval` was also designed with AI native coding in mind. We also include other
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
