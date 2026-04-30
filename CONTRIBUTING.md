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

If you're testing a change to a specific adapter (e.g. `smolagents`), make sure the matching extra is installed (`uv sync --extra smolagents`) — adapter modules import their respective frameworks at module load time and will skip if unavailable.

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
- **`pathlib.Path`**, never `os.path`.
- **f-strings**, never `%` or `.format()`.
- **Comprehensions over loops** — prefer `[x for x in ...]` and `asyncio.gather(*(coro for ...))` over `for ... append`.
- **Comments only for the WHY**, never the WHAT. Names should be self-documenting; don't write multi-line comment blocks.
- **No mocking of internal modules in tests** — exercise the public interface.

The full Python style guide lives in [`CLAUDE.md`](CLAUDE.md).

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
