# pytest-agent-eval — Claude Code Guidelines

Every rule below exists because something in this repo went wrong without it. Where a
rule has a non-obvious reason, the reason is stated — follow the reason, not the letter.

## Typing

- **Never `typing.Any`.** It silently switches off checking, and neither `ty` nor ruff's
  `ANN401` catches `dict[str, Any]`. Instead:
  - a third-party value → **the real SDK type under `TYPE_CHECKING`.** This is the
    default. Check whether the package ships `py.typed` before assuming it doesn't:
    openai, langchain-core, pydantic-ai and livekit do; **smolagents does not**.
  - a genuinely untyped dependency → a `Protocol` for what you actually call.
  - JSON → `JsonMapping`.
  - a foreign object you want to attach state to → `pytest.StashKey[T]`, never `setattr`.
  - `object`, then narrow with `isinstance` — the fallback of last resort, not the
    default. Only where a third party's own generic or hook signature dictates the slot,
    or where the value really is arbitrary (a parsed YAML document).

  Both residues are enumerated in `tests/test_public_surface.py` (`ANY_ALLOWLIST`,
  `OBJECT_ALLOWLIST`) with what forces each one; adding to either is a one-line diff a
  reviewer sees. `OBJECT_ALLOWLIST` also fails on a *stale* entry, so a residue a refactor
  closed cannot linger as false debt.

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

  **The same trap sits one level up, in a third party's own invariant generic.**
  `Runnable[Input, Output]` is invariant in both, so `Runnable[dict[str, JsonValue], str]`
  rejects a real `RunnableLambda`. Don't tighten a type argument you did not declare.

  `tests/adapters/_sdk_probe.py` assigns a real SDK object to every adapter's declared
  parameter type and is type-checked by `tests/adapters/test_sdk_types.py`. That static
  check is the only thing that catches either failure — the adapter still imports and
  passes every fake-based test while being unusable from a typed call site.
  `_sdk_probe_negative.py` inverts it: the test asserts that file *fails* to type-check for
  two named diagnostics, which is how "why not just `asdict(message)`?" gets answered by
  the checker rather than by a comment.

- **Put the type on the parameter.** A `client: object` parameter with a `cast(...)` in the
  body is an unchecked assertion, not a type. Use the real SDK type under `TYPE_CHECKING`,
  or a Protocol (spelled per the rule above) where the SDK ships no types.
  `openai.AsyncOpenAI` could not be a Protocol even if we wanted one, because `create` is
  overloaded. `hasattr` guards stay regardless: they name the extra to install, which an
  assignability error does not.

- **Every Protocol must be named by an annotation.** One that isn't is documentation the
  checker never verifies — three had drifted out of use and two of them described a shape
  the real class could not have satisfied.

- **No `cast()`.** Construct the type instead: `{str(k): v for k, v in raw.items()}` builds
  a `ToolArgs` where `cast("ToolArgs", raw)` merely claimed one. If a value's type is
  genuinely unknown, narrow it with `isinstance` per hop — the cast that replaced
  `_last_message` asserted three facts and checked one.

- **Closed string sets are `Literal` aliases**, never a bare `str` documented in prose —
  see `ToolCallArgsMode`, `OutcomeName`, `PhaseName`.

- **Aliases live in one module** (`models.py`), except an SDK-specific one, which belongs
  beside its adapter (`AnyAgent`, `LangChainRunnable`). A bare `X = dict[str, object]` is
  enough — `ty` infers the alias, so the `: TypeAlias` annotation buys nothing here and is
  deprecated in favour of 3.12's `type` statement, which this project cannot use yet.
  Never re-spell a structural type inline twice. ABCs come from `collections.abc`. No
  string-quoted annotations.

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

- **No trivial indirection** — the rule is about what a function *adds*, not how short it
  is. A one-liner that only renames an expression earns nothing: `_type_name(x)` was
  `type(x).__name__` at ten call sites, and `_get_agent()` was a pure alias for the
  `_agent` cached_property beside it. Inline or delete those. If inlining would duplicate
  a decision, bind it once instead — `ContainsEvaluator.evaluate` binds `fold` rather than
  spelling the case-sensitivity ternary four times, and `langchain._tool_calls` binds how a
  LangChain tool call maps onto ours rather than spelling it in both branches of `__call__`.

  **A private one-liner with no docstring is the tell.** Every one that proved removable
  had that shape: `report._xdist_active` / `_is_xdist_controller` (a two-deep alias chain),
  `_reasoning_lines` (one use), `livekit._quiet_livekit_loggers` (one caller), and
  `yaml_loader._validate` (a pass-through with no production caller).

  **Exempt, because the name is buying something:**
  - `@property` / `@cached_property` — a property *is* the interface.
  - anything memoised or expensive. A one-liner that hides real cost is worth its name, and
    inlining it hides the cost instead: `report._group_results` re-aggregates every outcome
    and is called three times a session; `AudioSynthesizer.synthesize` is a network
    round-trip; `_make_wav_file_audio_input_class` is `functools.cache` around a deferred
    livekit import.
  - a DI or monkeypatch seam a test substitutes (`synthesize`, `WavFileAudioInput`).
  - `...` Protocol stubs, dunder and protocol methods, and pytest hooks.
  - a one-liner whose *rule* needs stating: `groups._matches_identity` is one line, but the
    parametrisation-aware `entry + "["` prefix is exactly the kind of thing that gets
    "simplified" to `startswith(entry)` and starts matching `test_books_and_cancels`.

  Where a one-liner is kept, the docstring says which of these it is.
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
uv run pytest tests/ -q                                            # 458 tests
uv run coverage run -m pytest tests/ && uv run coverage report      # 100%, gated
uv run pytest tests/ -n auto -q                                     # xdist path (no --cov)
uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/
uv run ty check src/ --exit-zero-on-warning
uv run pre-commit run --all-files
```

## Attribution

Do not add `Co-Authored-By` trailers to commits or PRs.
