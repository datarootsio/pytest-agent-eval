# voice-livekit

Voice evals: each turn declares an `audio:` WAV that the `LiveKitAdapter` streams into a fresh LiveKit `AgentSession`; tool calls and the assistant transcript feed the same evaluators as text agents.

```bash
pip install 'pytest-agent-eval[livekit]'
export OPENAI_API_KEY=...

# Generate the WAV fixtures from each turn's user text (hash-cached)
python -m pytest_agent_eval.synthesize_audio

pytest --agent-eval-live
```

This example needs live credentials and generated audio, so the repository's CI only checks that it collects.
