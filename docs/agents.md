# Using with coding agents

pytest-agent-eval is built to be authored by LLMs as much as by people: transcripts are plain YAML with a published schema, error messages name the field and suggest the fix, and the whole documentation ships in agent-ingestible form.

Point your coding agent (Claude Code, Cursor, Copilot, ...) at these resources:

- **[`llms.txt`](https://datarootsio.github.io/pytest-agent-eval/llms.txt)** — the index, at the site root per the [llms.txt convention](https://llmstxt.org/)
- **[`llms-full.txt`](https://datarootsio.github.io/pytest-agent-eval/llms-full.txt)** — the entire documentation as one file, for tools that ingest a single URL
- **[JSON Schema](https://datarootsio.github.io/pytest-agent-eval/schema/transcript.json)** — machine-readable transcript format
- **[`examples/`](https://github.com/datarootsio/pytest-agent-eval/tree/main/examples)** — small runnable projects, one per feature

## AGENTS.md snippet

Paste this into your repository's `AGENTS.md` / `CLAUDE.md` so agents write correct evals on the first try:

````markdown
## Writing agent evals (pytest-agent-eval)

Prefer YAML transcripts over Python tests. Put them in the directory named by
`yaml_dirs` under `[tool.agent_eval]` in pyproject.toml (default: tests/evals/);
each file becomes a pytest test automatically. Start every file with:

    # yaml-language-server: $schema=https://datarootsio.github.io/pytest-agent-eval/schema/transcript.json

Canonical multi-turn transcript:

    id: booking_flow            # unique; becomes the test name
    threshold: 0.66             # fraction of runs that must pass
    runs: 3
    tags: [gate:booking]        # feeds [tool.agent_eval.groups] CI gates
    turns:
      - user: "Book me a slot tomorrow at 10am."
        expect:
          reply_contains_any: [confirmed, booked]
          tool_calls_include: [create_booking]
          tool_calls_args:
            - tool: create_booking
              args: {time: "10am"}          # subset match (mode: exact for equality)
      - user: "Actually make it 11am."
        expect:
          tool_calls_include: [update_booking]
          tool_calls_exclude: [create_booking]
          judge:
            rubric: "Confirms the new time and references the original booking."

All expect fields (each optional): reply_contains_any, reply_contains_all,
reply_matches_any, reply_matches_all (regex via re.search), tool_calls_include,
tool_calls_exclude, tool_calls_ordered (bool), tool_calls_args (tool/args/mode/judge),
judge (rubric/model).

Evaluator cheat-sheet: contains/matches = deterministic string checks on the reply;
tool_calls_* = which tools ran, their order, and their arguments; judge = LLM-graded
rubric (costs tokens; prefer deterministic checks when possible).

Gotchas:
- Eval tests are SKIPPED unless run with `--agent-eval-live` or `EVAL_LIVE=1`.
  "N eval test(s) skipped — live mode is off" in the output means they did not run.
- A conftest.py fixture named `llm_eval_agent` must return the agent under test:
  an async callable `(messages) -> (reply, tool_calls)`. Framework adapters exist
  for pydantic-ai, LangChain, OpenAI, smolagents, and LiveKit.

Reference: https://datarootsio.github.io/pytest-agent-eval/llms.txt (index),
https://datarootsio.github.io/pytest-agent-eval/schema/transcript.json (schema),
https://github.com/datarootsio/pytest-agent-eval/tree/main/examples (runnable examples).
````

## Why agents do well with this plugin

- **Schema-first authoring** — the `yaml-language-server` directive plus `additionalProperties: false` means invalid files fail loudly, not silently.
- **Didactic errors** — a typo'd field produces `turns[0].expect: unknown field 'tool_call_include'. Did you mean 'tool_calls_include'?` with the full valid-field list, which agents self-correct from.
- **Runnable examples** — every feature has a minimal project under [`examples/`](https://github.com/datarootsio/pytest-agent-eval/tree/main/examples) that CI keeps working, so copied code starts from a known-good state.
