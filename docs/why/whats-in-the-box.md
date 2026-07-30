# What else is in the box

`adapters`

:   **pydantic-ai, LangChain, the OpenAI SDK, smolagents, LiveKit**, or any async callable of your own that matches the contract

`python`

:   **`@pytest.mark.agent_eval` with `Turn` and `Expect`**: the same surface in code, if you prefer it to YAML

`parallel`

:   **`pytest -n auto`**: xdist works, and workers forward their results so the gates aggregate on the controller exactly as they would single-process

`reports`

:   **`--agent-eval-report=eval.md`**: a per-run, per-turn trace including every judge's reasoning, for attaching to a CI job

`gates`

:   **aggregate CI thresholds**: `must_pass` pins, and an exit code overridden to 0 once every failure is one a gate absorbed

`cost safety`

:   **nothing bills you by accident**: eval tests skip unless `--agent-eval-live` or `EVAL_LIVE=1` says otherwise

`custom checks`

:   **your own evaluator**: anything satisfying the `Evaluator` protocol composes with the built-ins on the same turn

`voice`

:   **the LiveKit adapter**: a WAV per turn through a real `AgentSession`, evaluated by the same evaluators as text

`audio`

:   **`synthesize_audio`**: turns the `user` text of a voice transcript into WAVs, cached by hash so it only re-synthesises what changed

```console
$ python -m pytest_agent_eval.synthesize_audio tests/evals/

Synthesized 0 new WAVs, 2 already up to date.

$ pytest --agent-eval-live -q tests/evals/booking_voice.yaml
.                                                          [100%]
1 passed in 18.2s
```

## Start small, add tiers as you need them

One transcript is enough to start. Add the directory, write a single YAML file with one turn and
one substring check, and you have a test that runs in the same command as the rest of your suite,
and stays skipped until you ask it to cost money.

Add the middle tier when the substring check starts lying to you. Add a judge when you genuinely
cannot express what you want any other way. Add a group gate on the day the flakiness first makes
someone want to delete the whole folder.

## Go deeper

- [Getting started](../getting-started.md): the full walkthrough
- [Examples](../examples.md): one runnable project per feature
- [Adapters](../adapters.md): including [LiveKit voice](../adapters.md#livekit-voice)
- [Reporting](../reporting.md): verbosity levels and the markdown report
