# Configuration

All configuration lives under `[tool.agent_eval]` in `pyproject.toml`.

## Complete example

```toml
[tool.agent_eval]
model     = "openai:gpt-4o"
threshold = 0.8
runs      = 3
retries   = 2
timeout   = 30
yaml_dirs = ["tests/evals"]
live      = false
```

## Fields

### `model`

**Type:** `str`
**Default:** `"openai:gpt-4o"`

The pydantic-ai model ID used by `JudgeEvaluator` and for YAML-defined judge rubrics.
Format is `provider:model-name`, e.g.:

- `"openai:gpt-4o"`
- `"openai:gpt-4o-mini"`
- `"anthropic:claude-3-5-sonnet-latest"`

### `threshold`

**Type:** `float`
**Default:** `0.8`

The default pass fraction across runs. A test passes when `passed_runs / total_runs >= threshold`.

Individual tests override this via `@pytest.mark.agent_eval(threshold=0.9)` or the YAML `threshold` field.

### `runs`

**Type:** `int`
**Default:** `3`

The default number of times each transcript is executed. Higher values reduce the impact of nondeterminism but increase cost.

Individual tests override this via `@pytest.mark.agent_eval(runs=5)` or the YAML `runs` field.

### `retries`

**Type:** `int`
**Default:** `2`

Number of times to retry a single run if the agent raises an exception (network error, rate limit, etc.).

### `timeout`

**Type:** `int`
**Default:** `30`

Per-turn timeout in seconds. If the agent callable does not return within this window, the turn is marked as failed.

### `yaml_dirs`

**Type:** `list[str]`
**Default:** `[]`

Directories to search recursively for `*.yaml` evaluation transcripts. Paths are relative to the project root (where `pyproject.toml` lives).

### `live`

**Type:** `bool`
**Default:** `false`

When `true`, eval tests run without needing `--agent-eval-live` or `EVAL_LIVE=1`. Useful for local development but should remain `false` in shared/CI config.

## Precedence

Command-line flag `--agent-eval-live` > `EVAL_LIVE=1` env var > `live = true` in config > default (skip).

Per-test `threshold`/`runs` in the mark or YAML always override the global config values.
