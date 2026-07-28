from pathlib import Path

import pytest

from pytest_agent_eval.evaluators.contains import ContainsEvaluator
from pytest_agent_eval.evaluators.tool_call import ToolCallEvaluator
from pytest_agent_eval.models import (
    Expect,
    Transcript,
    TranscriptResult,
    Turn,
)
from pytest_agent_eval.runner import EvalSession, JudgeSettings, TranscriptRunner, run_transcript
from tests.helpers.agents import RecordingAgent, ScriptedAgent, booking_agent, echo_agent
from tests.helpers.judge import FailingJudge, PromptCapturingJudge


@pytest.mark.asyncio
async def test_turn_audio_is_forwarded_to_the_agent_as_a_message_key() -> None:
    """Voice adapters read the WAV path off the user message; it must be a str, not a Path."""
    agent = RecordingAgent()

    transcript = Transcript(id="voice", turns=[Turn(user="book me", audio=Path("turn1.wav"))], threshold=0.0)
    await run_transcript(transcript, agent)

    assert agent.last_message["audio"] == "turn1.wav"
    assert isinstance(agent.last_message["audio"], str)
    assert agent.last_message["content"] == "book me"


@pytest.mark.asyncio
async def test_turn_without_audio_omits_the_key_entirely() -> None:
    """An absent audio key is what tells a text adapter this is not a voice turn."""
    agent = RecordingAgent()

    await run_transcript(Transcript(id="text", turns=[Turn(user="hi")], threshold=0.0), agent)

    assert "audio" not in agent.last_message


@pytest.mark.asyncio
async def test_run_transcript_single_turn_passes() -> None:
    transcript = Transcript(
        id="test",
        turns=[Turn(user="hello")],
        threshold=0.8,
        runs=1,
    )
    result = await run_transcript(transcript, echo_agent)
    assert isinstance(result, TranscriptResult)
    assert result.passed is True
    assert result.score == 1.0
    assert len(result.runs) == 1


@pytest.mark.asyncio
async def test_run_transcript_with_contains_evaluator() -> None:
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
    result = await run_transcript(transcript, booking_agent)
    assert result.passed is True
    assert result.runs[0].turn_results[0].passed is True


@pytest.mark.asyncio
async def test_run_transcript_with_tool_call_evaluator() -> None:
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
    result = await run_transcript(transcript, booking_agent)
    assert result.passed is True


@pytest.mark.asyncio
async def test_run_transcript_builds_contains_evaluator_from_regex_expect() -> None:
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
    result = await run_transcript(transcript, booking_agent)
    assert result.passed is True

    failing = Transcript(
        id="regex_fail",
        turns=[Turn(user="book me", expect=Expect(reply_matches_all=[r"BK-\d+"]))],
        threshold=1.0,
        runs=1,
    )
    result = await run_transcript(failing, booking_agent)
    assert result.passed is False


@pytest.mark.asyncio
async def test_run_transcript_enforces_tool_calls_ordered_from_expect() -> None:
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
async def test_run_transcript_fails_when_evaluator_fails() -> None:
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
    result = await run_transcript(transcript, booking_agent)
    assert result.passed is False
    assert result.score == 0.0


@pytest.mark.asyncio
async def test_run_transcript_multiple_runs_score() -> None:
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
    flaky = ScriptedAgent(replies=["error occurred", "confirmed booking", "error occurred", "confirmed booking"])
    result = await run_transcript(transcript, flaky)
    assert result.score == 0.5
    assert result.passed is True  # 0.5 >= 0.5


@pytest.mark.asyncio
async def test_runner_normalises_plain_strings_to_tool_calls() -> None:
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
async def test_run_transcript_dispatches_tool_calls_args_deterministic() -> None:
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
async def test_run_transcript_dispatches_tool_calls_args_judge_with_model_fallback() -> None:
    """config_model reaches the args judge — asserted by handing it a model that records use."""
    from pytest_agent_eval.models import JudgeConfig, ToolCall, ToolCallArgsConfig

    async def args_agent(history: list[dict]) -> tuple[str, list]:
        return "done", [ToolCall("book_slot", {"time": "10am"})]

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
    fallback = PromptCapturingJudge(passed=True, reasoning="ok")

    result = await run_transcript(transcript, args_agent, config_model=fallback.model)

    assert result.passed is True
    # The fallback model was the one actually invoked, and it saw the rubric.
    assert "Business hours only" in fallback.last_prompt


@pytest.mark.asyncio
async def test_per_turn_judge_model_overrides_the_config_model() -> None:
    """Precedence is turn override, then judge_model, then config_model."""
    from pytest_agent_eval.models import JudgeConfig

    chosen = PromptCapturingJudge(reasoning="from the turn override")
    ignored = PromptCapturingJudge(reasoning="from config")
    transcript = Transcript(
        id="override",
        turns=[Turn(user="hi", expect=Expect(judge=JudgeConfig(rubric="r", model=chosen.model)))],
        threshold=0.0,
        runs=1,
    )

    await run_transcript(transcript, echo_agent, config_model=ignored.model)

    assert chosen.prompts
    assert ignored.prompts == []


@pytest.mark.asyncio
async def test_run_transcript_passes_judge_retries_and_timeout_through() -> None:
    from pytest_agent_eval.models import JudgeConfig

    transcript = Transcript(
        id="judge_knobs",
        turns=[Turn(user="hi", expect=Expect(judge=JudgeConfig(rubric="anything")))],
        threshold=0.0,
        runs=1,
    )
    judge = FailingJudge(error="API down")

    await run_transcript(transcript, echo_agent, config_model=judge.model, judge_retries=0, judge_timeout=5.0)

    assert judge.attempts == 1


@pytest.mark.asyncio
async def test_history_is_accumulated_across_turns() -> None:
    agent = RecordingAgent()

    transcript = Transcript(
        id="multi",
        turns=[Turn(user="first"), Turn(user="second")],
        runs=1,
    )
    await run_transcript(transcript, agent)
    assert len(agent.seen[0]) == 1
    assert len(agent.seen[1]) == 3
    assert agent.seen[1][-1]["content"] == "second"


def test_judge_settings_resolve_model_precedence() -> None:
    """One place now decides the judge model: turn override, then judge_model, then config_model."""
    settings = JudgeSettings(config_model="from-config", judge_model="from-judge-model")

    assert settings.resolve_model("from-the-turn") == "from-the-turn"
    assert settings.resolve_model() == "from-judge-model"
    assert JudgeSettings(config_model="from-config").resolve_model() == "from-config"
    assert JudgeSettings().resolve_model() is None


@pytest.mark.asyncio
async def test_run_transcript_rejects_an_unknown_judge_keyword() -> None:
    """A typo'd judge knob must still fail loudly, as a plain parameter list did."""
    transcript = Transcript(id="typo", turns=[Turn(user="hi")], threshold=0.0, runs=1)

    with pytest.raises(TypeError, match="unexpected keyword argument 'judge_retires'"):
        await run_transcript(transcript, echo_agent, judge_retires=0)


@pytest.mark.asyncio
async def test_transcript_runner_runs_a_transcript_directly() -> None:
    """The class is the API the wrapper delegates to; it must work on its own."""
    runner = TranscriptRunner(echo_agent, JudgeSettings())

    result = await runner.run(Transcript(id="direct", turns=[Turn(user="hello")], threshold=1.0, runs=2))

    assert result.passed is True
    assert len(result.runs) == 2


@pytest.mark.asyncio
async def test_eval_session_run_stores_result_on_item() -> None:
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


@pytest.mark.asyncio
async def test_eval_session_without_an_item_still_returns_a_result() -> None:
    """The Python API is usable outside a pytest item; there is then nothing to stash onto."""
    session = EvalSession(threshold=0.0, runs=1)
    result = await session.run(echo_agent, [Turn(user="hello")])
    assert isinstance(result, TranscriptResult)
    assert result.passed is True
