"""Contract tests: adapters and judge against real installed SDK objects, no network.

The fake-based adapter tests pin our behavior; these pin the SDKs' shapes. When a
lockfile bump changes a message class or attribute name, these fail instead of the
drift going unnoticed (which is how the pydantic-ai all_messages() regression
slipped through). LiveKit stays fake-based: its event objects require a running
session to construct.
"""

from __future__ import annotations

import types

from pytest_agent_eval.models import TurnContext

# --- pydantic-ai: real Agent + TestModel end-to-end ---


async def test_pydantic_ai_adapter_against_real_agent():
    from pydantic_ai import Agent
    from pydantic_ai.models.test import TestModel

    from pytest_agent_eval.adapters.pydantic_ai import PydanticAIAdapter

    agent = Agent(TestModel())

    @agent.tool_plain
    def book_slot(time: str) -> str:
        """Book a slot at the given time."""
        return f"booked {time}"

    adapter = PydanticAIAdapter(agent)
    reply, tool_calls = await adapter([{"role": "user", "content": "book me"}])

    assert isinstance(reply, str) and reply
    assert tool_calls == ["book_slot"]
    assert isinstance(tool_calls[0].args, dict)
    assert "time" in tool_calls[0].args


async def test_judge_evaluator_against_real_agent_with_structured_output():
    from pydantic_ai.models.test import TestModel

    from pytest_agent_eval.evaluators.judge import JudgeEvaluator

    model = TestModel(custom_output_args={"passed": True, "reasoning": "meets the rubric"})
    ev = JudgeEvaluator(rubric="Reply must be helpful", model=model)
    result = await ev.evaluate(TurnContext(user="hi", reply="hello!", tool_calls=[], history=[]))

    assert result.passed is True
    assert result.reasoning == "meets the rubric"


async def test_tool_call_args_judge_against_real_agent():
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


def _real_chat_completion() -> object:
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


async def test_openai_adapter_against_real_response_objects():
    from pytest_agent_eval.adapters.openai import OpenAIAdapter

    completion = _real_chat_completion()

    class FakeClient:
        class chat:
            class completions:
                @staticmethod
                async def create(**kwargs):
                    return completion

    reply, tool_calls = await OpenAIAdapter(FakeClient(), model="gpt-4o")([{"role": "user", "content": "book"}])

    assert reply == "Booking it now."
    assert tool_calls == ["book_slot"]
    assert tool_calls[0].args == {"time": "10am"}


# --- langchain-core: real AIMessage, both adapter branches ---


async def test_langchain_adapter_against_real_aimessage():
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

    reply, tool_calls = await LangChainAdapter(direct)([{"role": "user", "content": "book"}])
    assert reply == "Booked!"
    assert tool_calls == ["book_slot"]
    assert tool_calls[0].args == {"time": "10am"}

    graph = types.SimpleNamespace()

    async def ainvoke_graph(payload):
        return {"messages": [message]}

    graph.ainvoke = ainvoke_graph

    reply, tool_calls = await LangChainAdapter(graph)([{"role": "user", "content": "book"}])
    assert reply == "Booked!"
    assert tool_calls[0].args == {"time": "10am"}


# --- smolagents: real memory-step and ToolCall classes ---


async def test_smolagents_adapter_against_real_memory_objects():
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

    reply, tool_calls = await SmolagentsAdapter(fake_agent)([{"role": "user", "content": "book"}])

    assert reply == "Booked!"
    assert tool_calls == ["book_slot"]
    assert tool_calls[0].args == {"time": "10am"}
