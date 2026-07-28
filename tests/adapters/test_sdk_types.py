"""The guard rail: no adapter may reject the real SDK class its own docstring names.

Two halves, because the failure has two halves. ``_sdk_probe.py`` is type-checked by ``ty``
here, which is the only way to catch an invariant Protocol member — the adapter still
imports and passes every fake-based test while being unusable from a typed call site. The
constructor test then does the runtime half: a ``hasattr`` guard that turns a real object
away. The first of those two shipped once and had to be hot-fixed.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).parent.parent.parent
_PROBE = Path("tests") / "adapters" / "_sdk_probe.py"

_SDKS = ("openai", "langchain_core", "smolagents", "livekit.agents", "pydantic_ai")


def _ty() -> str:
    """Absolute path to the ty binary, preferring the one in this interpreter's venv."""
    local = Path(sys.executable).parent / "ty"
    return str(local) if local.exists() else (shutil.which("ty") or "")


def test_every_adapter_accepts_its_real_sdk_type() -> None:
    """Type-check the probe. A failure here means a Protocol rejects the class it describes."""
    for module in _SDKS:
        pytest.importorskip(module)
    ty = _ty()
    if not ty:
        pytest.skip("ty is not installed")

    # Trusted argv, no shell: the binary is resolved above and the path is a repo constant.
    result = subprocess.run(  # noqa: S603
        [ty, "check", str(_PROBE), "--output-format", "concise"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, (
        f"tests/adapters/_sdk_probe.py does not type-check, so an adapter's declared "
        f"parameter type rejects a real SDK object:\n{result.stdout}{result.stderr}"
    )


def test_every_adapter_constructor_accepts_a_real_sdk_object() -> None:
    """The runtime half: a hasattr guard must not turn away a genuine SDK instance."""
    for module in _SDKS:
        pytest.importorskip(module)

    from langchain_core.runnables import RunnableLambda
    from livekit.agents.voice import Agent as LiveKitAgent
    from livekit.agents.voice import AgentSession
    from openai import AsyncOpenAI
    from pydantic_ai import Agent as PydanticAgent
    from pydantic_ai.models.test import TestModel
    from smolagents import ToolCallingAgent
    from smolagents.models import Model

    from pytest_agent_eval.adapters.langchain import LangChainAdapter
    from pytest_agent_eval.adapters.livekit import LiveKitAdapter
    from pytest_agent_eval.adapters.openai import OpenAIAdapter
    from pytest_agent_eval.adapters.pydantic_ai import PydanticAIAdapter
    from pytest_agent_eval.adapters.smolagents import SmolagentsAdapter

    # Every one of these is offline: no request is made until the adapter is called.
    OpenAIAdapter(AsyncOpenAI(api_key="not-used"), model="gpt-4o")
    LangChainAdapter(RunnableLambda(lambda payload: payload))
    SmolagentsAdapter(ToolCallingAgent(tools=[], model=Model()))
    PydanticAIAdapter(PydanticAgent(TestModel()))
    LiveKitAdapter(lambda: (AgentSession(), LiveKitAgent(instructions="hi")))
