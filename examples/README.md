# Examples

Small, self-contained projects — one per feature. CI exercises every one of them (see `tests/test_examples.py`), so they are always a known-good starting point to copy from. Two caveats: judge rubrics are stubbed in CI (running those examples standalone needs an API key), and `voice-livekit` is collect-only in CI since it needs live credentials and synthesized audio.

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

Each example except `voice-livekit` uses a deterministic mock agent — swap the `llm_eval_agent` fixture for a real adapter to test your own agent. To run one:

```bash
cd examples/single-turn
pip install pytest-agent-eval   # or: uv add pytest-agent-eval
pytest --agent-eval-live
```
