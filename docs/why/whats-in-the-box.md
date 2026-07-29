# What else is in the box

`voice`

:   **the LiveKit adapter** — a WAV per turn through a real `AgentSession`, evaluated by the same evaluators as text

`parallel`

:   **`pytest -n auto`** — xdist works, and group gates aggregate across workers

`reports`

:   **`--agent-eval-report=eval.md`** — a per-run trace with the judge's reasoning

`python`

:   **`Turn`, `Expect`, `parametrize`** — the same surface in code, if you prefer it to YAML

Recording pending: `beat-10-voice.cast` — optional, target 0:20, 90 cols.

```console
$ python -m pytest_agent_eval.synthesize_audio
  ✓ tests/evals/booking_voice.yaml  → turn-01.wav, turn-02.wav  (cached)

$ pytest --agent-eval-live -q tests/evals/booking_voice.yaml
.                                                          [100%]
1 passed in 18.2s
```

Monday morning:

```console
$ uv add pytest-agent-eval
$ mkdir -p tests/evals
$ printf '\n[tool.agent_eval]\nyaml_dirs = ["tests/evals"]\n' >> pyproject.toml
$ pytest --agent-eval-live
```

## The argument

One transcript is enough to start. Add the directory, write a single YAML file with one turn and
one substring check, and you have a test that runs in the same command as the rest of your suite —
and stays skipped until you ask it to cost money.

Add the middle tier when the substring check starts lying to you. Add a judge when you genuinely
cannot express what you want any other way. Add a group gate on the day the flakiness first makes
someone want to delete the whole folder.

## Go deeper

- [Getting started](../getting-started.md) — the full walkthrough
- [Examples](../examples.md) — one runnable project per feature
- [Adapters](../adapters.md) — including [LiveKit voice](../adapters.md#livekit-voice)
