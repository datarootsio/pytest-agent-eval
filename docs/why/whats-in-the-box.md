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

:   **nothing bills you by accident**: eval tests skip unless `--agent-eval-live` or `EVAL_LIVE=1` says otherwise — the first command below collects a voice eval with no credentials in the environment and skips it

`custom checks`

:   **your own evaluator**: anything satisfying the `Evaluator` protocol composes with the built-ins on the same turn

`voice`

:   **the LiveKit adapter**: a WAV per turn through a real `AgentSession`, evaluated by the same evaluators as text

`audio`

:   **`synthesize_audio`**: turns the `user` text of a voice transcript into WAVs, cached by hash so it only re-synthesises what changed (the run below starts from an empty directory, so both turns are new; a second run prints `Synthesized 0 new WAVs, 2 already up to date.` and stops there)

<figure class="why-cast">
<div class="why-cast-mount"
     data-cast-id=""
     data-cast-slug="09-voice-eval"
     data-cast-poster="npt:0:02"
     role="img"
     aria-label="A voice transcript is collected without credentials and skipped, then synthesize_audio writes one WAV per turn and reports what it did, and finally the voice eval runs live through the LiveKit adapter and passes."></div>
<figcaption>asciinema: <code>synthesize_audio</code>, then a voice eval</figcaption>
</figure>

??? note "Transcript"

    ```console
    $ pytest --collect-only -q
    tests/evals/booking_voice.yaml::booking_voice

    1 eval test(s) skipped: live mode is off. Pass --agent-eval-live or set EVAL_LIVE=1.
    1 test collected in 0.00s

    $ python -m pytest_agent_eval.synthesize_audio tests/evals/
    synthesised    tests/evals/turn-01.wav
    synthesised    tests/evals/turn-02.wav

    Synthesized 2 new WAVs, 0 already up to date.
    Wrote .gitignore in tests/evals (*.wav, *.wav.hash) — generated audio is local-only;
    commit YAML transcripts only.

    $ pytest --agent-eval-live -q
    .                                                                        [100%]
    1 passed in 25.31s
    ```

Monday morning — `uv init` first if there is no project yet, then four commands. The last
one collects nothing, because `tests/evals` is still empty; that is exactly where the next
section starts.

<figure class="why-cast">
<div class="why-cast-mount"
     data-cast-id=""
     data-cast-slug="10-install"
     data-cast-poster="npt:0:02"
     role="img"
     aria-label="An empty project gets pytest-agent-eval added with uv, a tests/evals directory, and three lines appended to pyproject.toml. The first run finds no transcripts yet, which is where the next section picks up."></div>
<figcaption>asciinema: four commands, from an empty project to the first run</figcaption>
</figure>

??? note "Transcript (package versions as resolved on the day)"

    ```console
    $ uv init
    Initialized project `monday`

    $ uv add pytest-agent-eval
    Using CPython 3.14.2
    Creating virtual environment at: .venv
    Resolved 108 packages in 49ms
    Installed 102 packages in 404ms
     + aiofile==3.11.1
     + annotated-types==0.8.0
     ... 98 more
     + pytest-agent-eval==0.3.0

    $ mkdir -p tests/evals

    $ printf '\n[tool.agent_eval]\nyaml_dirs = ["tests/evals"]\n' >> pyproject.toml

    $ uv run pytest --agent-eval-live
    ============================= test session starts ==============================
    platform darwin -- Python 3.14.2, pytest-9.1.1, pluggy-1.6.0
    configfile: pyproject.toml
    plugins: agent-eval-0.3.0, logfire-4.39.0, anyio-4.14.2
    collected 0 items

    ============================ no tests ran in 0.00s =============================
    ```

!!! warning "`uv run pytest`, not bare `pytest`"

    `uv add` creates `.venv` but does not activate it, so a bare `pytest` on a clean machine
    is `command not found` — or worse, silently runs some other pytest that has never heard
    of this plugin. `uv run` is what puts the project's own interpreter in front of you, and
    the `platform` line above is how you check: it must name the version `uv add` reported.

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
