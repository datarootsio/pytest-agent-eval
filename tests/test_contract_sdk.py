"""Contract tests: adapters and judge against real installed SDK objects, no network.

The fake-based adapter tests pin our behavior; these pin the SDKs' shapes. When a
lockfile bump changes a message class or attribute name, these fail instead of the
drift going unnoticed (which is how the pydantic-ai all_messages() regression
slipped through). LiveKit stays fake-based: its event objects require a running
session to construct.
"""

from __future__ import annotations

import types
from typing import TYPE_CHECKING

import pytest

from pytest_agent_eval.models import Message, TurnContext

if TYPE_CHECKING:
    # The real SDK types, so the helpers below say what they build. Every runtime import
    # stays inside the test that needs it: this module must import without the extras.
    from langchain_core.messages import BaseMessage
    from openai.types.chat import ChatCompletion

# --- pydantic-ai: real Agent + TestModel end-to-end ---


async def test_pydantic_ai_adapter_against_real_agent() -> None:
    from pydantic_ai import Agent
    from pydantic_ai.models.test import TestModel

    from pytest_agent_eval.adapters.pydantic_ai import PydanticAIAdapter

    agent = Agent(TestModel())

    @agent.tool_plain
    def book_slot(time: str) -> str:
        """Book a slot at the given time."""
        return f"booked {time}"

    adapter = PydanticAIAdapter(agent)
    reply, tool_calls = await adapter([Message(role="user", content="book me")])

    assert isinstance(reply, str) and reply
    assert tool_calls == ["book_slot"]
    assert isinstance(tool_calls[0].args, dict)
    assert "time" in tool_calls[0].args


async def test_pydantic_ai_adapter_against_real_agent_multi_turn() -> None:
    """Regression: pydantic-ai's message_history takes ModelMessage objects, not OpenAI dicts.

    Passing raw dicts crashes with AttributeError on pydantic-ai 1.x+; the fake-based
    tests never exercised a real Agent with prior-turn history, so the drift was invisible.
    """
    from pydantic_ai import Agent
    from pydantic_ai.models.test import TestModel

    from pytest_agent_eval.adapters.pydantic_ai import PydanticAIAdapter

    adapter = PydanticAIAdapter(Agent(TestModel()))
    history = [
        Message(role="user", content="first turn"),
        Message(role="assistant", content="acknowledged"),
        Message(role="user", content="second turn"),
    ]
    reply, tool_calls = await adapter(history)

    assert isinstance(reply, str) and reply
    assert isinstance(tool_calls, list)


async def test_pydantic_ai_adapter_preserves_system_prompt_across_turns() -> None:
    """message_history reconstruction must re-embed the agent's static system prompt.

    pydantic-ai only auto-applies system_prompt when message_history is empty, so a
    naive reconstruction runs turn 2+ without it — a silent behavior change.
    """
    from pydantic_ai import Agent
    from pydantic_ai.messages import ModelResponse, TextPart
    from pydantic_ai.models.function import FunctionModel

    saw_system: list[bool] = []

    def model_fn(messages, info):
        saw_system.append(
            any(
                any(getattr(p, "part_kind", None) == "system-prompt" for p in getattr(m, "parts", [])) for m in messages
            )
        )
        return ModelResponse(parts=[TextPart(content="reply")])

    from pytest_agent_eval.adapters.pydantic_ai import PydanticAIAdapter

    adapter = PydanticAIAdapter(Agent(FunctionModel(model_fn), system_prompt="You are a pirate."))
    await adapter(
        [
            Message(role="user", content="turn 1"),
            Message(role="assistant", content="prev reply"),
            Message(role="user", content="turn 2"),
        ]
    )
    assert saw_system == [True]


def test_pydantic_ai_adapter_excludes_native_tool_search() -> None:
    """builtin-tool-call covers native tool-search meta-ops; those must not be counted."""
    from pytest_agent_eval.adapters.pydantic_ai import _is_tool_call_part

    class _NativeToolCallPart:
        part_kind = "builtin-tool-call"

    class _NativeToolSearchCallPart:
        part_kind = "builtin-tool-call"

    class _ToolCallPart:
        part_kind = "tool-call"

    class _TextPart:
        part_kind = "text"

    assert _is_tool_call_part(_NativeToolCallPart()) is True
    assert _is_tool_call_part(_ToolCallPart()) is True
    assert _is_tool_call_part(_NativeToolSearchCallPart()) is False
    assert _is_tool_call_part(_TextPart()) is False


async def test_judge_evaluator_against_real_agent_with_structured_output() -> None:
    from pydantic_ai.models.test import TestModel

    from pytest_agent_eval.evaluators.judge import JudgeEvaluator

    model = TestModel(custom_output_args={"passed": True, "reasoning": "meets the rubric"})
    ev = JudgeEvaluator(rubric="Reply must be helpful", model=model)
    result = await ev.evaluate(TurnContext(user="hi", reply="hello!", tool_calls=[], history=[]))

    assert result.passed is True
    assert result.reasoning == "meets the rubric"


async def test_tool_call_args_judge_against_real_agent() -> None:
    from pydantic_ai.models.test import TestModel

    from pytest_agent_eval.evaluators.judge import ToolCallArgsJudgeEvaluator
    from pytest_agent_eval.models import ToolCall

    model = TestModel(custom_output_args={"passed": False, "reasoning": "time out of range"})
    ev = ToolCallArgsJudgeEvaluator(tool="book_slot", rubric="Business hours only", model=model)
    ctx = TurnContext(user="hi", reply="ok", tool_calls=[ToolCall("book_slot", {"time": "3am"})], history=[])
    result = await ev.evaluate(ctx)

    assert result.passed is False
    assert result.reasoning == "time out of range"


# --- openai: real response pydantic objects through a fake client ---


def _real_chat_completion() -> ChatCompletion:
    """Build the SDK's own response object, so the adapter is read against the real shape.

    The return type is the real class under ``TYPE_CHECKING`` while the runtime import
    stays inside the body: this module must import without the openai extra, which the
    ``test-no-extras`` job enforces.
    """
    from openai.types.chat import ChatCompletion, ChatCompletionMessage
    from openai.types.chat.chat_completion import Choice

    try:
        from openai.types.chat import ChatCompletionMessageFunctionToolCall as ToolCallType
        from openai.types.chat.chat_completion_message_function_tool_call import Function
    except ImportError:
        from openai.types.chat import ChatCompletionMessageToolCall as ToolCallType
        from openai.types.chat.chat_completion_message_tool_call import Function

    return ChatCompletion(
        id="chatcmpl-test",
        object="chat.completion",
        created=0,
        model="gpt-4o",
        choices=[
            Choice(
                index=0,
                finish_reason="tool_calls",
                message=ChatCompletionMessage(
                    role="assistant",
                    content="Booking it now.",
                    tool_calls=[
                        ToolCallType(
                            id="call_1",
                            type="function",
                            function=Function(name="book_slot", arguments='{"time": "10am"}'),
                        )
                    ],
                ),
            )
        ],
    )


async def test_openai_adapter_against_real_response_objects() -> None:
    pytest.importorskip("openai")
    from pytest_agent_eval.adapters.openai import OpenAIAdapter

    completion = _real_chat_completion()

    class FakeClient:
        class chat:
            class completions:
                @staticmethod
                async def create(**kwargs):
                    return completion

    reply, tool_calls = await OpenAIAdapter(FakeClient(), model="gpt-4o")([Message(role="user", content="book")])

    assert reply == "Booking it now."
    assert tool_calls == ["book_slot"]
    assert tool_calls[0].args == {"time": "10am"}


# --- langchain-core: real AIMessage, both adapter branches ---


async def test_langchain_adapter_against_real_aimessage() -> None:
    pytest.importorskip("langchain_core")
    from langchain_core.messages import AIMessage

    from pytest_agent_eval.adapters.langchain import LangChainAdapter

    message = AIMessage(
        content="Booked!",
        tool_calls=[{"name": "book_slot", "args": {"time": "10am"}, "id": "call_1"}],
    )

    direct = types.SimpleNamespace()

    async def ainvoke_direct(payload):
        return message

    direct.ainvoke = ainvoke_direct

    reply, tool_calls = await LangChainAdapter(direct)([Message(role="user", content="book")])
    assert reply == "Booked!"
    assert tool_calls == ["book_slot"]
    assert tool_calls[0].args == {"time": "10am"}

    graph = types.SimpleNamespace()

    async def ainvoke_graph(payload):
        return {"messages": [message]}

    graph.ainvoke = ainvoke_graph

    reply, tool_calls = await LangChainAdapter(graph)([Message(role="user", content="book")])
    assert reply == "Booked!"
    assert tool_calls[0].args == {"time": "10am"}


# --- smolagents: real memory-step and ToolCall classes ---


async def test_smolagents_adapter_against_real_memory_objects() -> None:
    pytest.importorskip("smolagents")
    from smolagents.memory import ActionStep
    from smolagents.memory import ToolCall as SmolToolCall
    from smolagents.monitoring import Timing

    from pytest_agent_eval.adapters.smolagents import SmolagentsAdapter

    step = ActionStep(
        step_number=1,
        timing=Timing(start_time=0.0, end_time=1.0),
        tool_calls=[SmolToolCall(name="book_slot", arguments={"time": "10am"}, id="call_1")],
    )

    fake_agent = types.SimpleNamespace()
    fake_agent.memory = types.SimpleNamespace(steps=[])

    def run(task: str, reset: bool = True) -> str:
        fake_agent.memory.steps = [step]
        return "Booked!"

    fake_agent.run = run

    reply, tool_calls = await SmolagentsAdapter(fake_agent)([Message(role="user", content="book")])

    assert reply == "Booked!"
    assert tool_calls == ["book_slot"]
    assert tool_calls[0].args == {"time": "10am"}


async def test_langchain_adapter_history_survives_real_message_coercion() -> None:
    """The adapter forwards history into the runnable, where LangChain coerces it.

    langchain_core.convert_to_messages() raises NotImplementedError on a Mapping that is
    not a dict, so Message must be converted at this boundary. A fake runnable cannot
    catch that — it never coerces anything.
    """
    pytest.importorskip("langchain_core")
    from langchain_core.messages import AIMessage, convert_to_messages

    from pytest_agent_eval.adapters.langchain import LangChainAdapter

    coerced: list[BaseMessage] = []

    class CoercingRunnable:
        async def ainvoke(self, payload: dict) -> object:
            coerced.extend(convert_to_messages(payload["messages"]))
            return AIMessage(content="Booked!", tool_calls=[])

    reply, _ = await LangChainAdapter(CoercingRunnable())([Message(role="user", content="book me", audio="turn1.wav")])

    assert reply == "Booked!"
    assert [type(m).__name__ for m in coerced] == ["HumanMessage"]
    # The plugin-internal audio key must not reach the framework either.
    assert not any("turn1.wav" in str(m) for m in coerced)
