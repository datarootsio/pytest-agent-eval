# One contract. Three places to run it.

```python
async def agent(history: History) -> AgentReply
```

- `History` = `list[Message]` — read it as `history[-1].content`
- `Message` is a frozen dataclass of `role`, `content`, `audio`, and *also* a `Mapping`, so
  `history[-1]["content"]` reads the same value and compares equal to the plain dict it replaced
- `AgentReply` is a `NamedTuple(reply, tool_calls)`, exported from `pytest_agent_eval`
- `ToolCalls` = `Sequence[str]`, not `list[str]` — `list` is invariant, so `list[ToolCall]` would
  not be assignable to `list[str]` even though `ToolCall` subclasses `str`
- `AgentCallable` = `Callable[[History], Awaitable[tuple[str, ToolCalls]]]` — declared as the plain
  tuple, so an adapter returning `AgentReply` and a hand-written agent returning `(str, list[str])`
  both satisfy one alias

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

The types are named rather than anonymous, and each name buys something without taking anything
away. `Message` is a dataclass you read as `.content`, but it is also a `Mapping`, so every agent
written against the old plain dict keeps working. `AgentReply` is a `NamedTuple`, so
`reply, tool_calls = await agent(history)` still destructures — and the contract stays the wider
plain tuple, so returning one is still valid. Even the tool calls stayed permissive: bare names get
the name checks, `ToolCall(name, args)` lights up the argument checks on the same suite, because a
`ToolCall` *is* a `str`. **Naming the types did not narrow what the plugin accepts.**

The other half is where these tests are allowed to cost money. Eval tests **skip unless you ask**,
via `--agent-eval-live` or `EVAL_LIVE=1`. That default is what makes it safe for an eval suite to
live in the same repo, and the same `pytest` invocation, as your unit tests.

## Go deeper

- [Adapters](../adapters.md) — every framework, and writing a custom adapter
- [API reference — Models](../api-reference/models.md) — `Message`, `AgentReply`, `ToolCall`
- [Configuration](../configuration.md) — `live`, `runs`, `model`
