import pytest

from pytest_agent_eval.evaluators.contains import ContainsEvaluator
from pytest_agent_eval.evaluators.tool_call import ToolCallEvaluator
from pytest_agent_eval.models import (
    Expect,
    Transcript,
    TranscriptResult,
    Turn,
)
from pytest_agent_eval.runner import EvalSession, run_transcript


async def _echo_agent(history: list[dict]) -> tuple[str, list[str]]:
    """Agent that echoes the last user message."""
    return history[-1]["content"], []


async def _booking_agent(history: list[dict]) -> tuple[str, list[str]]:
    """Agent that returns a booking confirmation."""
    return "Your slot is confirmed for tomorrow at 10am.", ["book_slot"]


@pytest.mark.asyncio
async def test_run_transcript_single_turn_passes():
    transcript = Transcript(
        id="test",
        turns=[Turn(user="hello")],
        threshold=0.8,
        runs=1,
    )
    result = await run_transcript(transcript, _echo_agent)
    assert isinstance(result, TranscriptResult)
    assert result.passed is True
    assert result.score == 1.0
    assert len(result.runs) == 1


@pytest.mark.asyncio
async def test_run_transcript_with_contains_evaluator():
    transcript = Transcript(
        id="test",
        turns=[
            Turn(
                user="book me a slot",
                expect=Expect(evaluators=[ContainsEvaluator(any_of=["confirmed"])]),
            )
        ],
        threshold=1.0,
        runs=1,
    )
    result = await run_transcript(transcript, _booking_agent)
    assert result.passed is True
    assert result.runs[0].turn_results[0].passed is True


@pytest.mark.asyncio
async def test_run_transcript_with_tool_call_evaluator():
    transcript = Transcript(
        id="test",
        turns=[
            Turn(
                user="book me",
                expect=Expect(evaluators=[ToolCallEvaluator(must_include=["book_slot"])]),
            )
        ],
        threshold=1.0,
        runs=1,
    )
    result = await run_transcript(transcript, _booking_agent)
    assert result.passed is True


@pytest.mark.asyncio
async def test_run_transcript_builds_contains_evaluator_from_regex_expect():
    transcript = Transcript(
        id="regex",
        turns=[
            Turn(
                user="book me",
                expect=Expect(reply_matches_any=[r"\bconfirmed\b"], reply_matches_all=[r"\d{1,2}am"]),
            )
        ],
        threshold=1.0,
        runs=1,
    )
    result = await run_transcript(transcript, _booking_agent)
    assert result.passed is True

    failing = Transcript(
        id="regex_fail",
        turns=[Turn(user="book me", expect=Expect(reply_matches_all=[r"BK-\d+"]))],
        threshold=1.0,
        runs=1,
    )
    result = await run_transcript(failing, _booking_agent)
    assert result.passed is False


@pytest.mark.asyncio
async def test_run_transcript_enforces_tool_calls_ordered_from_expect():
    async def ordered_agent(history: list[dict]) -> tuple[str, list[str]]:
        return "done", ["fetch", "auth"]

    transcript = Transcript(
        id="ordered",
        turns=[Turn(user="go", expect=Expect(tool_calls_include=["auth", "fetch"], tool_calls_ordered=True))],
        threshold=1.0,
        runs=1,
    )
    result = await run_transcript(transcript, ordered_agent)
    assert result.passed is False

    unordered = Transcript(
        id="unordered",
        turns=[Turn(user="go", expect=Expect(tool_calls_include=["auth", "fetch"]))],
        threshold=1.0,
        runs=1,
    )
    result = await run_transcript(unordered, ordered_agent)
    assert result.passed is True


@pytest.mark.asyncio
async def test_run_transcript_fails_when_evaluator_fails():
    transcript = Transcript(
        id="test",
        turns=[
            Turn(
                user="book me",
                expect=Expect(evaluators=[ContainsEvaluator(any_of=["cancelled"])]),
            )
        ],
        threshold=1.0,
        runs=1,
    )
    result = await run_transcript(transcript, _booking_agent)
    assert result.passed is False
    assert result.score == 0.0


@pytest.mark.asyncio
async def test_run_transcript_multiple_runs_score():
    call_count = 0

    async def flaky_agent(history: list[dict]) -> tuple[str, list[str]]:
        nonlocal call_count
        call_count += 1
        if call_count % 2 == 0:
            return "confirmed booking", []
        return "error occurred", []

    transcript = Transcript(
        id="flaky",
        turns=[
            Turn(
                user="book",
                expect=Expect(evaluators=[ContainsEvaluator(any_of=["confirmed"])]),
            )
        ],
        threshold=0.5,
        runs=4,
    )
    result = await run_transcript(transcript, flaky_agent)
    assert result.score == 0.5
    assert result.passed is True  # 0.5 >= 0.5


@pytest.mark.asyncio
async def test_runner_normalises_plain_strings_to_tool_calls():
    from pytest_agent_eval.models import EvalResult, ToolCall

    captured: list[list] = []

    class CaptureEvaluator:
        async def evaluate(self, ctx):
            captured.append(ctx.tool_calls)
            return EvalResult(passed=True)

    async def mixed_agent(history: list[dict]) -> tuple[str, list]:
        return "ok", ["plain_name", ToolCall("with_args", {"a": 1})]

    transcript = Transcript(
        id="normalise",
        turns=[Turn(user="go", expect=Expect(evaluators=[CaptureEvaluator()]))],
        runs=1,
    )
    await run_transcript(transcript, mixed_agent)
    tool_calls = captured[0]
    assert all(isinstance(tc, ToolCall) for tc in tool_calls)
    assert tool_calls[0].args is None
    assert tool_calls[1].args == {"a": 1}


@pytest.mark.asyncio
async def test_run_transcript_dispatches_tool_calls_args_deterministic():
    from pytest_agent_eval.models import ToolCall, ToolCallArgsConfig

    async def args_agent(history: list[dict]) -> tuple[str, list]:
        return "done", [ToolCall("book_slot", {"time": "10am"})]

    transcript = Transcript(
        id="args_ok",
        turns=[
            Turn(
                user="book",
                expect=Expect(tool_calls_args=[ToolCallArgsConfig(tool="book_slot", args={"time": "10am"})]),
            )
        ],
        threshold=1.0,
        runs=1,
    )
    result = await run_transcript(transcript, args_agent)
    assert result.passed is True

    mismatch = Transcript(
        id="args_bad",
        turns=[
            Turn(
                user="book",
                expect=Expect(tool_calls_args=[ToolCallArgsConfig(tool="book_slot", args={"time": "11am"})]),
            )
        ],
        threshold=1.0,
        runs=1,
    )
    result = await run_transcript(mismatch, args_agent)
    assert result.passed is False


@pytest.mark.asyncio
async def test_run_transcript_dispatches_tool_calls_args_judge_with_model_fallback():
    from unittest.mock import AsyncMock, MagicMock, patch

    from pytest_agent_eval.models import JudgeConfig, ToolCall, ToolCallArgsConfig

    async def args_agent(history: list[dict]) -> tuple[str, list]:
        return "done", [ToolCall("book_slot", {"time": "10am"})]

    mock_output = MagicMock()
    mock_output.passed = True
    mock_output.reasoning = "ok"
    mock_result = MagicMock()
    mock_result.output = mock_output

    transcript = Transcript(
        id="args_judge",
        turns=[
            Turn(
                user="book",
                expect=Expect(
                    tool_calls_args=[
                        ToolCallArgsConfig(tool="book_slot", judge=JudgeConfig(rubric="Business hours only"))
                    ]
                ),
            )
        ],
        threshold=1.0,
        runs=1,
    )

    with patch("pytest_agent_eval.evaluators.judge.Agent") as MockAgent:
        instance = AsyncMock()
        instance.run = AsyncMock(return_value=mock_result)
        MockAgent.return_value = instance
        result = await run_transcript(transcript, args_agent, config_model="openai:fallback-model")

    assert result.passed is True
    assert MockAgent.call_args.args[0] == "openai:fallback-model"


@pytest.mark.asyncio
async def test_history_is_accumulated_across_turns():
    captured_histories: list[list[dict]] = []

    async def capture_agent(history: list[dict]) -> tuple[str, list[str]]:
        captured_histories.append(list(history))
        return "ok", []

    transcript = Transcript(
        id="multi",
        turns=[Turn(user="first"), Turn(user="second")],
        runs=1,
    )
    await run_transcript(transcript, capture_agent)
    assert len(captured_histories[0]) == 1
    assert len(captured_histories[1]) == 3
    assert captured_histories[1][-1]["content"] == "second"


@pytest.mark.asyncio
async def test_eval_session_run_stores_result_on_item():
    """EvalSession.run() returns result and stores it on _item._eval_result."""
    import types

    async def agent(history: list[dict]) -> tuple[str, list[str]]:
        return "all good", []

    mock_item = types.SimpleNamespace()  # simple namespace that accepts arbitrary attributes
    session = EvalSession(threshold=0.0, runs=1, _item=mock_item)
    result = await session.run(agent=agent, turns=[Turn(user="hi")])

    assert result.passed is True
    assert hasattr(mock_item, "_eval_result")
    assert mock_item._eval_result is result
