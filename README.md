# pytest-llm-eval

[![PyPI version](https://img.shields.io/pypi/v/pytest-llm-eval.svg)](https://pypi.org/project/pytest-llm-eval/)
[![Python versions](https://img.shields.io/pypi/pyversions/pytest-llm-eval.svg)](https://pypi.org/project/pytest-llm-eval/)
[![License](https://img.shields.io/pypi/l/pytest-llm-eval.svg)](https://github.com/datarootsio/pytest-llm-eval/blob/main/LICENSE)
[![pytest plugin](https://img.shields.io/badge/pytest-plugin-0A9EDC?logo=pytest&logoColor=white)](https://docs.pytest.org/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://pre-commit.com/)

**LLM evaluation tests that actually mean something.** A pytest plugin for testing LLM agents with threshold-based pass/fail scoring, multi-turn transcripts, and LLM-as-judge rubrics — without breaking your CI bill.

## Highlights

- 🎯 **Threshold-based pass/fail** — run each test N times, pass when ≥ threshold% succeed
- 📝 **YAML or Python transcripts** — pick the authoring style your team prefers
- 🔍 **YAML auto-discovery** — drop `*.yaml` files in any configured directory and they become pytest tests automatically
- 🛡 **CI-safe by default** — eval tests skip unless `--llm-eval-live` or `EVAL_LIVE=1`
- ⚡ **Parallel-ready** — `pytest -n auto` (via [`pytest-xdist`](https://pytest-xdist.readthedocs.io/)) just works
- 📄 **Markdown reports** — full per-run trace with `--llm-eval-report=eval.md`

## Installation

```bash
# pip
pip install pytest-llm-eval

# uv
uv add pytest-llm-eval
```

## Supported frameworks

`pytest-llm-eval` ships first-class adapters for the major Python agent frameworks. Each is an optional extra so you only install what you use.

| Framework | Extra | Adapter |
|---|---|---|
| [pydantic-ai](https://ai.pydantic.dev/) | _(default)_ | `pytest_llm_eval.adapters.pydantic_ai.PydanticAIAdapter` |
| [LangChain / LangGraph](https://python.langchain.com/) | `langchain` | `pytest_llm_eval.adapters.langchain.LangChainAdapter` |
| [OpenAI SDK](https://github.com/openai/openai-python) | `openai` | `pytest_llm_eval.adapters.openai.OpenAIAdapter` |
| [smolagents](https://github.com/huggingface/smolagents) | `smolagents` | `pytest_llm_eval.adapters.smolagents.SmolagentsAdapter` |

```bash
pip install "pytest-llm-eval[langchain]"
pip install "pytest-llm-eval[openai]"
pip install "pytest-llm-eval[smolagents]"
# or with uv:
uv add "pytest-llm-eval[langchain]"
uv add "pytest-llm-eval[openai]"
uv add "pytest-llm-eval[smolagents]"
```

Bringing your own framework? Any `async def agent(messages) -> (reply, tool_calls)` callable works directly — no base class needed.

## What you can test

`pytest-llm-eval` separates the *kinds of checks* you might want into composable evaluators:

- **Deterministic checks** — `ContainsEvaluator(any_of=["confirmed", "booked"])` for substring/regex assertions over the agent reply.
- **Tool-call assertions** — `ToolCallEvaluator(must_include=["create_booking"], ordered=True)` to verify that the agent called the right tools, in the right order.
- **LLM-as-judge** — `JudgeEvaluator(rubric="Reply must be friendly, include a date, and confirm the booking.")` for open-ended quality checks the agent under test should meet.

Mix and match per turn — every evaluator participates in the threshold score.

## Quick start

```python
import pytest
from pytest_llm_eval import Turn, Expect, ContainsEvaluator, ToolCallEvaluator, JudgeEvaluator

@pytest.mark.llm_eval(threshold=0.8, runs=3)
async def test_booking(llm_eval):
    result = await llm_eval.run(
        agent=my_agent,
        turns=[
            Turn(
                user="Book me a slot tomorrow at 10am",
                expect=Expect(evaluators=[
                    ContainsEvaluator(any_of=["confirmed", "booked"]),
                    ToolCallEvaluator(must_include=["create_booking"]),
                    JudgeEvaluator(rubric="Reply must include a reference number."),
                ]),
            )
        ],
    )
    result.assert_threshold()
```

```bash
pytest --llm-eval-live
```

See the [full documentation](https://datarootsio.github.io/pytest-llm-eval) for the YAML authoring style, configuration, and reporting options.

## License

MIT — see [LICENSE](LICENSE).
