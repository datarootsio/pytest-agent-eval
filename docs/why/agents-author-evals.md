# And then the agent writes the *evals* too

Recording pending: `beat-09-authoring.cast` — target 0:45, 90 cols.

```console
$ claude
> write an eval for the reschedule flow. follow AGENTS.md.

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

`schema`

:   **a published JSON Schema** with `additionalProperties: false` — invalid files fail loudly, not silently

`errors`

:   **didactic by design** — `unknown field 'tool_call_include'. Did you mean 'tool_calls_include'?`, with the schema URL attached

`config`

:   **`[tool.agent_eval]` is strictly validated** — `threshold = "high"` is rejected at load, not deep inside a score comparison

`fixtures`

:   **the missing-fixture case is a message, not a crash** — it tells you which fixture and where to put it

`types`

:   **`py.typed` ships**, so the named contract reaches the agent's type checker too

`context`

:   **`llms.txt` and `llms-full.txt`** at the site root, plus an `AGENTS.md` snippet to paste

`examples`

:   **runnable projects CI keeps green** — copied code starts from a known-good state

## The argument

These pages opened with an agent writing an agent, and a test that was green for the wrong reason.
This is the same loop, closed properly: the agent writes the eval, and it is right the first
time — because YAML with a published schema and field-level error messages is a target an LLM can
actually hit.

That is not a happy accident, it is why the YAML surface exists at all. A typo'd field names
itself and suggests the fix, which is exactly the feedback shape a coding agent self-corrects
from. Forget the fixture and the plugin tells you which fixture and where to put it, rather than
dying with an internal error. Every decision here was made twice: once for the human reader, once
for the machine author.

Which is the honest reframing of the whole argument. **You are not writing tests to slow the agent
down. You are writing the thing that lets you let it go faster.**

## Go deeper

- [Using with coding agents](../agents.md) — the `AGENTS.md` snippet and schema-first authoring
- [YAML API](../yaml-api.md) — every transcript field the schema validates
- [Examples](../examples.md) — the runnable projects CI keeps green
