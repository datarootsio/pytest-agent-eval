import pytest
from pytest_llm_eval.models import (
    Transcript, Turn, Expect, TranscriptResult, EvalResult, TurnContext
)
from pytest_llm_eval.evaluators.contains import ContainsEvaluator
from pytest_llm_eval.evaluators.tool_call import ToolCallEvaluator
from pytest_llm_eval.runner import run_transcript


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
                expect=Expect(
                    evaluators=[ContainsEvaluator(any_of=["confirmed"])]
                ),
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
                expect=Expect(
                    evaluators=[ToolCallEvaluator(must_include=["book_slot"])]
                ),
            )
        ],
        threshold=1.0,
        runs=1,
    )
    result = await run_transcript(transcript, _booking_agent)
    assert result.passed is True


@pytest.mark.asyncio
async def test_run_transcript_fails_when_evaluator_fails():
    transcript = Transcript(
        id="test",
        turns=[
            Turn(
                user="book me",
                expect=Expect(
                    evaluators=[ContainsEvaluator(any_of=["cancelled"])]
                ),
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
