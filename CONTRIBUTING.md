# Contributing to pytest-agent-eval

Thanks for considering a contribution! This document covers everything you need to know to develop, test, and ship changes to `pytest-agent-eval`.

## Project layout

```text
pytest-agent-eval/
├── src/pytest_agent_eval/      # the plugin source (importable as `pytest_agent_eval`)
│   ├── adapters/               # framework adapters (pydantic-ai, langchain, openai, smolagents)
│   ├── evaluators/             # ContainsEvaluator, ToolCallEvaluator, JudgeEvaluator
│   ├── plugin.py               # pytest hooks: marker, fixture, CLI options
│   ├── runner.py               # transcript execution + threshold scoring
│   ├── yaml_loader.py          # auto-discovery of *.yaml transcripts
│   └── report.py               # markdown report writer
├── tests/                      # pytest test suite (no live LLM calls)
├── docs/                       # zensical-built docs
└── pyproject.toml              # source of truth for version, deps, entry point
```

## Prerequisites

- **Python ≥ 3.11** (required by `tomllib` and our type-annotation style).
- **[uv](https://docs.astral.sh/uv/getting-started/installation/)** as the package manager. Everything below assumes `uv` is on your `PATH`.
- A POSIX shell (`bash` / `zsh`). Windows works via WSL.

## Getting started

```bash
# 1. Fork and clone
git clone git@github.com:<your-fork>/pytest-agent-eval.git
cd pytest-agent-eval

# 2. Install the package + every optional extra + dev tooling
uv sync --all-extras --group dev

# 3. Install the pre-commit hooks (runs ruff + a few file-hygiene checks on every commit)
uv run pre-commit install
```

That's it — you now have an editable install with all adapter extras (`langchain`, `openai`, `smolagents`, `xdist`) and the dev toolchain available under `uv run`.

To verify the install:

```bash
uv run python -c "import pytest_agent_eval; print(pytest_agent_eval.__version__)"
# 0.1.0
```

## Running tests

The full test suite runs against unit-test fixtures — **no live LLM calls, no API keys required**:

```bash
uv run pytest tests/ -v
```

Run a single file or test:

```bash
uv run pytest tests/test_runner.py -v
uv run pytest tests/test_runner.py::test_history_is_accumulated_across_turns -v
```

In parallel:

```bash
uv run pytest tests/ -n auto
```

If you're testing a change to a specific adapter (e.g. `smolagents`), install the matching extra (`uv sync --extra smolagents`). Adapter modules do **not** import their frameworks — they are duck-typed and raise a `TypeError` naming the extra if handed the wrong object — so the adapter's own tests run either way. What needs the extra is the SDK *contract* tests in `tests/test_contract_sdk.py`, which construct real SDK objects and `importorskip` when the extra is missing. CI runs `uv sync --all-extras` and asserts those tests do not skip.

Coverage is deliberately extras-independent: the `test-no-extras` CI job reaches the same 100%, because the extras contribute no unique lines.

## Linting and formatting

Pre-commit runs `ruff check --fix` and `ruff format` on every commit, plus a handful of file-hygiene checks. To run the full suite manually:

```bash
uv run pre-commit run --all-files
```

Or just ruff:

```bash
uv run ruff check src/ tests/
uv run ruff format src/ tests/
```

Ruff config lives in `pyproject.toml` under `[tool.ruff]`. Line length is **120**.

### Style rules

These are enforced by ruff but worth knowing up front:

- **Type annotations on every function** — parameters and return types. Use `from __future__ import annotations` at the top of every file.
- **Never `typing.Any`.** Use `object` plus narrowing for unknown input, a `Protocol` for a duck-typed third-party object, the real type under `TYPE_CHECKING` when the dependency ships types, and `JsonMapping` for JSON. The remaining uses are allowlisted in `tests/test_public_surface.py`, and that list only shrinks.
- **Accept `Sequence`, return `list`.** `list` is invariant, which is the single biggest source of spurious type errors in this codebase.
- **`frozen=True, slots=True`** on records the plugin produces; types a *user* constructs stay mutable.
- **Pydantic at every external boundary** (YAML, TOML, CLI, LLM output) with `extra="forbid"`; plain dataclasses inside.
- **Return a record, never an anonymous tuple**, and never index one of our own records by string key — a `dict` is a serialisation format, produced at the edge by `to_dict()` / `model_dump()`.
- **`pathlib.Path`**, never `os.path`, and `Path.read_text()` rather than builtin `open()`.
- **f-strings**, never `%` or `.format()`.
- **Comprehensions over loops** — prefer `[x for x in ...]` and `asyncio.gather(*(coro for ...))` over `for ... append`.
- **Comments only for the WHY**, never the WHAT. Names should be self-documenting; don't write multi-line comment blocks.
- **No mocking of internal modules in tests** — exercise the public interface, and prefer a real test double from the library (pydantic-ai ships `TestModel` and `FunctionModel`). Where a test needs a seam, add the parameter.
- **Coverage is a 100% ratchet**, statements and branches. Measure with `coverage run -m pytest`, never `pytest --cov` — the plugin loads through its `pytest11` entry point before `pytest-cov` starts tracing, understating the total by ~15 points.

Two divergences from the wider house style are intentional: line length is **120** (reformatting to 88 would touch every file) and docstrings are **Google** style (`zensical.toml` sets `docstring_style = "google"`, so changing it breaks the published API reference).

`pyproject.toml` carries two explicit ratchets — per-file ruff ignores and demoted `ty` rules — each naming the refactor that closes it. They are meant to shrink.

The full Python style guide lives in [`CLAUDE.md`](CLAUDE.md).

## Recording the docs/why casts

Ten pages under `docs/why/` embed an asciinema recording of a real terminal session. The
recordings are real runs — where a recording and a page disagreed, the page was corrected,
not the recording. Until a cast is recorded and uploaded, its page renders an amber
"Recording pending" box naming the command that would fix it, so a missing cast is
self-documenting and never blocks a docs build.

**You do the typing.** Nothing here simulates a keystroke. Each cast is a directory holding
the real files that are on screen plus a `runsheet.txt` — the screenplay: the exact lines to
type, in order, and what each should print. `rec.sh` only *starts* the recording in the
right place with a clean prompt, then gets out of the way.

```bash
asciinema auth                        # STEP 0, ONCE, EVER. See the warning below.
uv sync --all-extras --group dev      # the repo's own venv — rec.sh activates it for you

cat docs/casts/03-runs-and-threshold/runsheet.txt   # read what you're about to type
docs/casts/rec.sh 03-runs-and-threshold             # drops you in, recording, prompt is `$ `
# ...you type the runsheet lines. Ctrl-D when done.
asciinema play docs/casts/03-runs-and-threshold.cast   # review; unhappy? just rerun rec.sh
docs/casts/upload.sh 03-runs-and-threshold          # prints the data-cast-id= line to paste
```

> **`asciinema auth` is not optional.** asciinema.org deletes any recording that is not
> linked to an account after 7 days. An uploaded-then-expired cast is worse than a missing
> one: the page renders a dead player instead of the placeholder that tells you how to fix
> it.

`docs/casts/casts.txt` is the inventory — one row per cast, giving its title and the page it
belongs to. `rec.sh --help` prints the slugs.

### What `rec.sh` does before handing you the keyboard

Four things, all of them off camera on purpose:

1. **Resets the cast directory** (`git checkout` + `git clean` on it). This is what makes a
   retake identical to a first take. Without it the second recording of `02-flaky-assert`
   starts from a warm counter file and fails on the wrong iterations.
2. **`cd`s in and activates the repo's root `.venv`.** So what you type on screen is the
   clean `pytest --agent-eval-live -vv` a reader would actually type — not `uv run pytest`.
   Recording against the editable install is also the right default: the cast shows the
   working tree, which is the version the docs are being built for.
3. **Sets `PS1='$ '`** and unsets `VIRTUAL_ENV_PROMPT`, so the prompt matches the `$ ` in
   every console block instead of showing your hostname, your cwd and a `(venv)` prefix.
4. **Starts the recording** in `zsh -f` at `--window-size 80x24` with
   `--idle-time-limit 1.5`.

zsh because it is the macOS default, so what a reader sees is the shell they actually have —
and because macOS's bash 3.2 prints *"The default interactive shell is now zsh … run `chsh`"*
on every interactive start, straight into the take. `--norc --noprofile` does not suppress
that; Apple patched it into the binary rather than into `/etc/profile`. `-f` is zsh's
equivalent of `--norc --noprofile`: it skips `.zshenv`, `.zprofile`, `.zshrc` and `.zlogin`,
so a take cannot pick up your aliases, plugins or prompt theme.

One shell for every cast rather than `$SHELL`, because the point is that two takes by two
people look the same. Set `CAST_SHELL` to override (`CAST_SHELL='bash --norc --noprofile'`),
and note the runsheets are all POSIX — the only shell-sensitive line is `10-install`'s
`printf`, which is byte-identical under both.

One window size for all ten, or the embedded players end up different widths and the pages
look ragged. 80 columns is what pytest's rule lines are already sized for and it stays
legible on a phone. `--idle-time-limit` is what makes hand-typing viable at all: it is
stored in the cast *header* and applied at **playback**, so your pauses while you find the
next line get capped without altering the capture — and it can be re-tuned afterwards by
editing the header, with no re-record.

### Two casts record in a throwaway directory

A cast whose directory holds nothing but its `runsheet.txt` records under `$TMPDIR` instead;
`rec.sh` works this out from the directory rather than from a second list. `10-install` is
one because it *is* `uv add` into an empty project. `07-agent-authors-eval` is one because
the Claude Code session needs an `AGENTS.md` beside it, and **no `.md` file may live
anywhere under `docs/casts/`** — any `.md` under `docs/` becomes a published, searchable
page even when it is absent from `nav`, and zensical 0.0.51 has no `exclude` option. That is
also why the runsheets are `.txt`.

### Casts that need credentials

Most casts are offline and byte-reproducible: the agent is a stub whose replies come from a
fixed list, so the run is real through the whole plugin but a retake looks the same as the
first take. Three are not, and each says so at the top of its runsheet:

| Cast | Needs |
|---|---|
| `05-judge-reasoning` | `OPENAI_API_KEY` — three `gpt-4o-mini` judge calls, well under a cent. A re-record produces *different* reasoning every time, which needs no follow-up: the page quotes no transcript, so the recording is the record. |
| `07-agent-authors-eval` | a real Claude Code session. Minutes, not seconds, and its output cannot be predicted. |
| `09-voice-eval` | one paid `synthesize_audio` run (the WAVs cannot be committed — the tool writes a `.gitignore` declaring generated audio local-only), then the `[livekit]` extra plus live OpenAI Realtime credentials. |

### Keeping a cast honest

`tests/test_casts.py` runs each fixture directory through `pytester` and pins its terminal
output with `fnmatch_lines`. If you change the plugin's output format, that test goes red
and tells you which cast now needs re-recording — which is the whole point of it. Walk the
runsheet by hand after any such change before reaching for the camera; a fixture whose stub
fails on the wrong iteration is much cheaper to find there than mid-take.

To check that a retake really is reproducible, record the same slug twice and diff the
plain-text renderings:

```bash
docs/casts/rec.sh 02-flaky-assert && cp docs/casts/02-flaky-assert.cast /tmp/a.cast
docs/casts/rec.sh 02-flaky-assert && cp docs/casts/02-flaky-assert.cast /tmp/b.cast
asciinema convert /tmp/a.cast /tmp/a.txt && asciinema convert /tmp/b.cast /tmp/b.txt
diff /tmp/a.txt /tmp/b.txt        # should differ only where a duration is printed
```

`.txt` selects the plain-text format automatically. Any *content* difference means
`rec.sh`'s reset is incomplete for that cast.

## Commit conventions

We use [Conventional Commits](https://www.conventionalcommits.org/). The first line of every commit is:

```text
<type>(<optional scope>): <short imperative summary>
```

Common types in this repo:

| Type     | Use for                                                              |
|----------|----------------------------------------------------------------------|
| `feat`   | New user-facing functionality                                        |
| `fix`    | Bug fix                                                              |
| `docs`   | Docs / README / CONTRIBUTING changes only                            |
| `refactor` | Internal restructure with no behavior change                       |
| `test`   | Adding or fixing tests                                               |
| `build`  | Build system, packaging, CI/CD config (e.g. `release.yml`)           |
| `chore`  | Lockfile updates, dep bumps, housekeeping                            |

Examples from the repo's history:

```text
feat: add SmolagentsAdapter shell with reset detection
docs: enrich README + docs with badges, framework + feature tabs
build: add CD release workflow and rename to pytest-agent-eval
```

**Don't add `Co-Authored-By` trailers** — see `CLAUDE.md`.

## Pull requests

1. Create a branch off `main` named after what you're doing: `feat/voice-adapter`, `fix/judge-timeout`, etc.
2. Make focused commits — one logical change per commit.
3. **Add or update tests** for any behavior change.
4. Run `uv run pytest tests/ -v` and `uv run pre-commit run --all-files` locally before pushing.
5. Open a PR against `main`. CI will run the test matrix (Python 3.11, 3.12, 3.13) and the lint job.
6. Address review comments by pushing additional commits — don't force-push to your PR branch unless asked.

For larger changes (new adapters, public API additions, anything touching `pyproject.toml` extras), open an issue first to discuss the design before writing code.

## Releasing to PyPI

Releases are fully automated — no manual `twine upload` or API tokens. The flow uses [PyPI Trusted Publishers](https://docs.pypi.org/trusted-publishers/) with GitHub OIDC, scoped to a `pypi` GitHub Environment.

### Procedure

Only repo maintainers can cut releases. Once your change is merged to `main`:

1. **Bump the version** in `pyproject.toml` following [SemVer](https://semver.org/):
   ```toml
   [project]
   version = "0.2.0"
   ```
2. **Commit and push to `main`**:
   ```bash
   git commit -am "release: 0.2.0"
   git push origin main
   ```
3. **Tag and push the tag** (the leading `v` is required):
   ```bash
   git tag v0.2.0
   git push origin v0.2.0
   ```
4. **Watch the workflow** at `https://github.com/datarootsio/pytest-agent-eval/actions`. The `Release` workflow runs four jobs in sequence:
   - `verify-version` — fails fast if the tag and `pyproject.toml` `version` disagree.
   - `build` — builds the sdist + wheel via `uv build`.
   - `publish-pypi` — publishes to PyPI via OIDC (no token).
   - `github-release` — creates a GitHub Release on the tag with auto-generated notes and the built artifacts attached.

The new version appears at <https://pypi.org/project/pytest-agent-eval/> within a minute of the workflow finishing.

### Common failure modes

- **Tag and `pyproject.toml` disagree** → `verify-version` exits with `Tag v0.2.0 does not match pyproject.toml version 0.1.9`. Fix the mismatch (most often: forgot to commit the bump before tagging) and re-tag.
- **`File already exists` from PyPI** → you tagged a version that's already published. PyPI never accepts re-uploads of the same version. Bump and retag.
- **`OIDC: invalid-publisher`** → the `pypi` GitHub Environment is missing or the Trusted Publisher record on PyPI doesn't match. See `.github/workflows/release.yml` and verify the registration at <https://pypi.org/manage/account/publishing/>.

### Why `__version__` doesn't need to change

`pytest_agent_eval.__version__` is read at import time from `importlib.metadata.version("pytest-agent-eval")`, which resolves to whatever was baked into the package metadata at build. The single source of truth is `pyproject.toml` `version` — there is no second literal to keep in sync.

## Backfilling docs for old releases

Documentation is published per-version to `gh-pages` via [`mike`](https://github.com/squidfunk/mike) (a fork maintained by squidfunk that integrates with zensical's version provider). The `docs.yml` workflow only runs on *future* pushes — pre-existing tags don't auto-publish. To populate the version dropdown with releases that were tagged before versioned docs were turned on, run a one-time backfill locally from a clean checkout:

```bash
uv sync --group docs
uv pip install git+https://github.com/squidfunk/mike.git

for tag in v0.1.0 v0.2.0; do
  git checkout "$tag"
  uv run mike deploy --push "$tag" $( [[ "$tag" == "v0.2.0" ]] && echo "latest" )
done
git checkout main
uv run mike deploy --push main
uv run mike set-default --push main
```

`--push` writes commits to the `gh-pages` branch directly, so push permissions on the repo are required. The newest tag is also aliased as `latest`, matching what `docs.yml` does on future tag pushes.

If an old tag's docs deps are no longer installable (e.g. zensical version drift), skip it — the dropdown will start at the oldest version that still builds.

## Community guidelines

This is an open, welcoming project. Specifically:

- **Be kind and patient** — assume good intent, especially in code review and issue threads.
- **No demographic-based commentary, harassment, or sustained disruption.** Maintainers will close threads and remove comments that violate this.
- **Disagreement is fine; rudeness is not.** If a discussion gets heated, take a breath, restate the technical question, and move on.
- **English is the working language** for issues, PRs, and code comments — but it doesn't have to be perfect. Effort matters more than fluency.

If you experience or witness behavior that doesn't fit the above, email <murilo@dataroots.io> directly. Reports are confidential and we'll respond within a few business days.

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
