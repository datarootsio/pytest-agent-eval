# pytest-llm-eval — Claude Code Guidelines

## Python Style

- **Type annotations**: All function parameters and return types must be annotated. Use `from __future__ import annotations` at the top of every file.
- **Dataclasses**: Use `@dataclass` for structured data. Avoid plain `dict` for typed records; use `dataclasses.field(default_factory=...)` for mutable defaults.
- **Comprehensions over loops**: Prefer list/dict/set comprehensions and generator expressions over `for` loops with `.append()`. For async operations, use `asyncio.gather(*(coro for ...))` instead of sequential awaits in a loop.
- **Pathlib**: Use `pathlib.Path` for filesystem paths. Never use `os.path`.
- **f-strings**: Use f-strings for all string formatting.
- **Comments**: Only comment non-obvious WHY (hidden constraints, subtle invariants, workarounds). Never comment what code does — names should be self-documenting. No multi-line comment blocks.
- **No unused imports**: Remove unused imports and variables immediately.
- **Line length**: 120 characters max (enforced by ruff).

## Async Patterns

- Use `asyncio.gather` for independent concurrent operations.
- Sequential `await` in a loop is only acceptable when operations have ordering dependencies (e.g., accumulated history across conversation turns).

## Testing

- Tests live in `tests/`. All tests use `pytest-asyncio` with `asyncio_mode = "auto"`.
- No mocking internal modules — test through the public interface.

## Running Tests and Linting

```bash
uv run pytest tests/ -v
uv run pre-commit run --all-files
```

## Attribution

Do not add `Co-Authored-By` trailers to commits or PRs.
