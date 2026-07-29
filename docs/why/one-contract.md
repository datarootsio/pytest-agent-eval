# One contract. Three places to run it.

```python
async def agent(messages: list[dict]) -> tuple[str, list[str]]
```

- `messages` — OpenAI-style history, `[{"role": "user", "content": "..."}, ...]`
- the return is `(reply_text, tool_names_called)` — a plain tuple of a string and a list
- to assert on arguments, return `ToolCall(name, args)` entries instead; `ToolCall` subclasses
  `str`, so everything that worked with plain names keeps working

`local`

:   **a few runs, cheap tiers only** — seconds, while you are editing a prompt

`pull request`

:   **gated groups, live mode off by default** — `--agent-eval-live` is opt-in, so a push never bills you

`nightly`

:   **high run counts, judges on, full report** — `-n auto` across xdist workers

## The argument

That signature is the whole plugin's surface area. Every adapter — pydantic-ai, LangChain, the
OpenAI SDK, smolagents, a LiveKit voice session — is a function of that shape. There is no base
class to inherit and nothing to register, which is why wrapping a backend you wrote yourself is
four lines.

It is deliberately the loosest contract that still supports every assertion on the previous pages.
Return bare tool names and the name checks work. Return `ToolCall(name, args)` and the argument
checks light up too, on the same suite, without changing anything else — because a `ToolCall` *is*
a `str`. **Richer assertions never demanded a richer contract.**

The other half is where these tests are allowed to cost money. Eval tests **skip unless you ask**,
via `--agent-eval-live` or `EVAL_LIVE=1`. That default is what makes it safe for an eval suite to
live in the same repo, and the same `pytest` invocation, as your unit tests.

## Go deeper

- [Adapters](../adapters.md) — every framework, and writing a custom adapter
- [API reference — Models](../api-reference/models.md) — `ToolCall` and its `.args`
- [Configuration](../configuration.md) — `live`, `runs`, `model`
