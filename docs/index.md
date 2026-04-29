# pytest-llm-eval

**LLM evaluation tests that actually mean something.**

`pytest-llm-eval` is a pytest plugin for testing LLM agents and applications
with threshold-based pass/fail scoring, multi-turn YAML transcripts, and
an LLM-as-judge rubric system.

## Highlights

- **Two authoring styles** — YAML transcripts or Python API
- **Nondeterminism-aware** — run each test N times, pass if ≥ threshold% succeed
- **CI-safe by default** — tests skip unless `--llm-eval-live` or `EVAL_LIVE=1`
- **Provider-agnostic** — bring your own agent callable; adapters for pydantic-ai, LangChain, OpenAI
- **Rich output** — score in terminal, full details with `-vv`, optional markdown report

## Quick start

```bash
pip install pytest-llm-eval
```

```python
import pytest
from pytest_llm_eval import Turn, Expect, ContainsEvaluator

@pytest.mark.llm_eval(threshold=0.8, runs=3)
async def test_booking(llm_eval):
    result = await llm_eval.run(
        agent=my_agent,
        turns=[Turn(user="Book me a slot", expect=Expect(
            evaluators=[ContainsEvaluator(any_of=["confirmed", "booked"])]
        ))],
    )
    result.assert_threshold()
```

```bash
pytest --llm-eval-live
```

See [Getting Started](getting-started.md) for a full walkthrough.
