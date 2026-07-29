"""Every adapter must reject a wrong object with a message naming the extra to install."""

import pytest

from pytest_agent_eval.adapters.langchain import LangChainAdapter
from pytest_agent_eval.adapters.openai import OpenAIAdapter
from pytest_agent_eval.adapters.pydantic_ai import PydanticAIAdapter
from pytest_agent_eval.adapters.smolagents import SmolagentsAdapter


def test_adapter_constructors_reject_wrong_objects() -> None:
    with pytest.raises(TypeError, match=r"ainvoke.*pytest-agent-eval\[langchain\]"):
        LangChainAdapter("not a runnable")
    with pytest.raises(TypeError, match=r"chat\.completions.*pytest-agent-eval\[openai\]"):
        OpenAIAdapter("not a client", model="gpt-4o")
    with pytest.raises(TypeError, match=r"pydantic-ai Agent"):
        PydanticAIAdapter("not an agent")
    with pytest.raises(TypeError, match=r"memory\.steps.*pytest-agent-eval\[smolagents\]"):
        SmolagentsAdapter("not an agent")
