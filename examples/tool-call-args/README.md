# tool-call-args

Assertions on the **arguments** a tool was called with: deterministic subset/exact checks plus an LLM-judged rubric. The mock agent returns `ToolCall(name, args)` objects — the same shape all bundled adapters produce.

```bash
export OPENAI_API_KEY=...        # only the judge entry needs it
pytest --agent-eval-live
```

The repository's CI runs this example with the judge stubbed.
