from pathlib import Path

import pytest

from pytest_agent_eval.models import (
    EvalResult,
    Expect,
    JudgeConfig,
    RunResult,
    ToolCall,
    Transcript,
    TranscriptResult,
    Turn,
    TurnContext,
    TurnResult,
)


def test_eval_result_defaults():
    r = EvalResult(passed=True)
    assert r.passed is True
    assert r.reasoning == ""


def test_turn_audio_defaults_none():
    t = Turn(user="hello")
    assert t.audio is None


def test_turn_audio_accepts_path():
    t = Turn(user="hello", audio=Path("foo.wav"))
    assert t.audio == Path("foo.wav")


def test_turn_audio_accepts_str():
    t = Turn(user="hello", audio="foo.wav")
    assert t.audio == "foo.wav"


def test_turn_context_fields():
    ctx = TurnContext(
        user="hello",
        reply="world",
        tool_calls=["tool_a"],
        history=[{"role": "user", "content": "hello"}],
    )
    assert ctx.user == "hello"
    assert ctx.tool_calls == ["tool_a"]


def test_tool_call_is_str_compatible():
    call = ToolCall("book_slot", {"date": "tomorrow"})
    assert call == "book_slot"
    assert call in ["book_slot", "other"]
    assert "book_slot" in [call]
    assert call.name == "book_slot"
    assert call.args == {"date": "tomorrow"}


def test_tool_call_args_default_to_none():
    call = ToolCall("book_slot")
    assert call.args is None


def test_transcript_result_passes_when_score_above_threshold():
    run = RunResult(
        run_index=0,
        passed=True,
        turn_results=[TurnResult(turn_index=0, passed=True, eval_results=[])],
    )
    result = TranscriptResult(passed=True, score=1.0, threshold=0.8, runs=[run])
    result.assert_threshold()  # should not raise


def test_transcript_result_fails_when_score_below_threshold():
    run = RunResult(
        run_index=0,
        passed=False,
        turn_results=[TurnResult(turn_index=0, passed=False, eval_results=[])],
    )
    result = TranscriptResult(passed=False, score=0.0, threshold=0.8, runs=[run])
    with pytest.raises(AssertionError, match="score=0.00 < threshold=0.80"):
        result.assert_threshold()


def test_transcript_defaults():
    t = Transcript(id="test", turns=[])
    assert t.threshold == 0.8
    assert t.runs == 1
    assert t.tags == []


def test_expect_defaults():
    e = Expect()
    assert e.evaluators == []
    assert e.tool_calls_include == []
    assert e.reply_contains_any == []


def test_judge_config():
    j = JudgeConfig(rubric="pass if helpful")
    assert j.model is None
