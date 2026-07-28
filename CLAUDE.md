# pytest-agent-eval — Claude Code Guidelines

Every rule below exists because something in this repo went wrong without it. Where a
rule has a non-obvious reason, the reason is stated — follow the reason, not the letter.

## Typing

- **Never `typing.Any`.** It silently switches off checking, and neither `ty` nor ruff's
  `ANN401` catches `dict[str, Any]`. Instead:
  - unknown input → `object`, then narrow. That forces the `isinstance` check `Any` lets
    you skip.
  - a duck-typed third-party object → a `Protocol` for what you actually call.
  - a dependency that ships types → the real type, imported under `TYPE_CHECKING`.
  - JSON → `JsonMapping`.
  - a foreign object you want to attach state to → `pytest.StashKey[T]`, never `setattr`.

  The remaining uses are enumerated in `tests/test_public_surface.py`. That allowlist only
  shrinks; adding to it is a one-line diff a reviewer sees, which is more than a
  `# type: ignore` would be.

- **Accept `Sequence`, return `list`.** `list` is invariant, so `list[ToolCall]` is not
  assignable to `list[str]` even though `ToolCall` subclasses `str`. That single fact
  caused six of the original type errors.

- **A Protocol's data members are `@property`, never a plain attribute.** A declared
  attribute is *invariant*, so no real class satisfies it: `memory: _AgentMemory` is a
  member a real `MultiStepAgent` fails, while `@property def memory(...)` is covariant and
  it passes. This has caused the same bug twice — once in a shipped release that had to be
  hot-fixed. Related: a Protocol method's parameter types are contravariant, so declaring
  `payload: Mapping[str, object]` where the real method takes a `dict` also rejects the
  real class. Type the parameter as what you actually pass.

  `tests/adapters/_sdk_probe.py` assigns a real SDK object to every adapter's declared
  parameter type and is type-checked by `tests/adapters/test_sdk_types.py`. That static
  check is the only thing that catches this — the adapter still imports and passes every
  fake-based test while being unusable from a typed call site.

- **Put the type on the parameter.** A `client: object` parameter with a `cast(...)` in the
  body is an unchecked assertion, not a type. Use a Protocol (spelled per the rule above),
  or the real SDK type under `TYPE_CHECKING` where a Protocol provably cannot express the
  surface — `openai.AsyncOpenAI` is the one such case, because `create` is overloaded.
  `hasattr` guards stay regardless: they name the extra to install, which an assignability
  error does not.

- **Every Protocol must be named by an annotation.** One that isn't is documentation the
  checker never verifies — three had drifted out of use and two of them described a shape
  the real class could not have satisfied.

- **No `cast()`.** Construct the type instead: `{str(k): v for k, v in raw.items()}` builds
  a `ToolArgs` where `cast("ToolArgs", raw)` merely claimed one. If a value's type is
  genuinely unknown, narrow it with `isinstance` per hop — the cast that replaced
  `_last_message` asserted three facts and checked one.

- **Closed string sets are `Literal` aliases**, never a bare `str` documented in prose —
  see `ToolCallArgsMode`, `OutcomeName`, `PhaseName`.

- **Aliases live in one module** (`models.py`). Never re-spell a structural type inline
  twice. ABCs come from `collections.abc`. No string-quoted annotations.

## Data

- **`@dataclass(frozen=True, slots=True)` for records the plugin produces** —
  `EvalResult`, `TurnResult`, `RunResult`, `TranscriptResult`, `GroupResult`, `Message`.
  Types a *user* constructs stay mutable, because building one up field by field is a
  reasonable thing to do. Both directions are asserted in `tests/test_public_surface.py`
  so the asymmetry reads as a decision.

- **Pydantic at every external boundary** — YAML, TOML, CLI args, LLM output — with
  `extra="forbid"` (except `[tool.agent_eval]`, where ignoring unknown keys is
  documented behaviour). Plain dataclasses inside. Do not put pydantic in the per-turn
  hot path, and never on `ToolCall`: it subclasses `str` with an out-of-band attribute
  and has no valid core schema.

- **Pydantic's lax mode is not your validation.** It reads `threshold: true` as `1.0` and
  `"0.5"` as `0.5`. Add a `mode="before"` validator for anything where a wrong type means
  the author meant something else.

- **Return a record, never an anonymous tuple.** `NamedTuple` only for a value we
  *produce* whose tuple shape is a back-compat contract (`AgentReply`); never for a value
  we *accept*, because a plain tuple is not a subtype of a NamedTuple and you would
  reject every existing caller.

- **A `dict` is a serialisation format, not a record type.** Produce it at the edge with
  `to_dict()` / `model_dump()`. Never index one of our own records by string key.

- When a record must stay dict-compatible for callers, make it a frozen dataclass that
  also implements `collections.abc.Mapping` with `eq=False`, so it compares equal to the
  dict it replaces (`Message`). Don't reach for `TypedDict`, and don't break the caller.

- **No attribute assigned in `__post_init__` that isn't a declared field.** It is
  invisible to `dataclasses.fields()` and silently blocks `slots`.

## Functions

- Guard clauses; nesting deeper than three is a smell. Enforced: complexity ≤ 8,
  ≤ 12 branches, ≤ 50 statements, ≤ 5 args.
- When three or more of the same parameters thread through a chain of functions, bundle
  them into a frozen settings dataclass or make the chain a class.
- **Docstring on every function, including private ones.**
- **No lazy-init `None` sentinel.** `functools.cache` at module level,
  `functools.cached_property` per instance.
- Never `global`.
- Comprehensions over `append` loops — except where order matters across iterations
  (the runner's accumulating `history`) or the body awaits, sleeps or `continue`s.

## Errors and IO

- `Path.read_text()` / `Path.open()`, never builtin `open()`.
- `except Exception` only for a deliberate retry or cleanup path, always with a comment
  saying which.
- A deferred import is fine but needs `# noqa: PLC0415` and a one-line why.
- `logging` with lazy `%s`; `print` only in a CLI entry point.
- Error messages are the product here. They name the location, say what a correct value
  looks like, and link the schema. This is why `EM` and `TRY003` are off.

## Packaging

- A typed library ships `py.typed`, or none of its annotations reach its users.

## Testing

- Tests live in `tests/`, mirroring `src/`. `pytest-asyncio` with `asyncio_mode = "auto"`.
- **No mocking internal modules.** Prefer a real test double from the library:
  pydantic-ai ships `TestModel` and `FunctionModel`, so `patch("...judge.Agent")` is both
  forbidden and unnecessary. Where a test needs a seam, **add the parameter** — don't
  monkeypatch a module attribute.
- Shared fakes and builders live in `tests/helpers/`, never duplicated per file. Fakes are
  typed classes or frozen dataclasses, not `SimpleNamespace` or mutable spy dicts. The two
  surviving `SimpleNamespace` fakes are commented: they exist because an attribute must be
  *absent*, which a dataclass cannot express.
- `parametrize` over near-identical bodies.
- **Coverage is a ratchet at 100%**, statements and branches, with every exclusion
  line-scoped and enumerated. Measure with `coverage run -m pytest`, never `pytest --cov`:
  the plugin loads through its `pytest11` entry point before `pytest-cov` starts tracing,
  which understates the total by ~15 points.
- Coverage must not depend on the optional extras. A `test-no-extras` CI job enforces it.
- 100% coverage without assertions is theatre. Before trusting the suite, mutate a few
  lines by hand and confirm each turns it red. That is how the missing assertion on the
  collect-error veto was found.

## Deliberate divergences from the global house style

Both are intentional; don't "fix" them.

- **Line length 120, not 88.** Reformatting would touch every file and destroy the
  reviewability of any change whose value is "no behaviour change".
- **Google docstrings, not reStructuredText.** `zensical.toml` sets
  `docstring_style = "google"` for mkdocstrings; changing it breaks the published API
  reference.
- `synthesize_audio.py` uses `print` because it is a CLI — stdout is the product.

## Running Tests and Linting

```bash
uv run pytest tests/ -q                                            # 436 tests
uv run coverage run -m pytest tests/ && uv run coverage report      # 100%, gated
uv run pytest tests/ -n auto -q                                     # xdist path (no --cov)
uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/
uv run ty check src/ --exit-zero-on-warning
uv run pre-commit run --all-files
```

## Attribution

Do not add `Co-Authored-By` trailers to commits or PRs.
