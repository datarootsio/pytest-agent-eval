# multi-turn-judge

A multi-turn conversation where turn 2 is graded by an LLM judge rubric alongside deterministic tool-call checks.

```bash
export OPENAI_API_KEY=...        # the judge makes a real LLM call
pytest --agent-eval-live
```

The repository's CI runs this example with the judge stubbed, so the transcript itself stays verified offline.
