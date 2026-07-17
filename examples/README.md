# Examples

Small, self-contained projects — one per feature. CI runs every one of them (see `tests/test_examples.py`), so they are always a known-good starting point to copy from.

| Example | Shows |
|---|---|
| [`single-turn/`](single-turn/) | The minimal setup: one YAML transcript, one fixture |
| [`multi-turn-judge/`](multi-turn-judge/) | Multi-turn conversation with an LLM-as-judge rubric |
| [`tool-calls/`](tool-calls/) | Tool-call assertions: include, exclude, ordered |
| [`tool-call-args/`](tool-call-args/) | Assertions on tool-call arguments (subset/exact + judge) |
| [`regex-contains/`](regex-contains/) | Substring and regex reply assertions |
| [`python-parametrize/`](python-parametrize/) | The Python API with `@pytest.mark.parametrize` |
| [`groups/`](groups/) | Group-level pass thresholds and the exit-code override |
| [`voice-livekit/`](voice-livekit/) | Voice evals driving a LiveKit `AgentSession` from WAVs |

Each example uses a deterministic mock agent so it runs offline — swap the `llm_eval_agent` fixture for a real adapter to test your own agent. To run one:

```bash
cd examples/single-turn
pip install pytest-agent-eval   # or: uv add pytest-agent-eval
pytest --agent-eval-live
```
