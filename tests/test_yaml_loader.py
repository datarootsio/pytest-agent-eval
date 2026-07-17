from pathlib import Path

import pytest

from pytest_agent_eval.yaml_loader import load_transcript

SAMPLE = Path(__file__).parent / "fixtures" / "sample_transcript.yaml"


def test_load_transcript_parses_fields():
    t = load_transcript(SAMPLE)
    assert t.id == "sample_booking"
    assert t.threshold == 1.0
    assert t.runs == 1
    assert t.tags == ["gate:booking"]
    assert len(t.turns) == 1
    assert t.turns[0].user == "Book me a slot"
    assert t.turns[0].expect.reply_contains_any == ["confirmed", "booked"]
    assert t.turns[0].expect.tool_calls_include == ["book_slot"]


def test_load_transcript_parses_regex_expect_fields(tmp_path: Path):
    yaml_path = tmp_path / "regex.yaml"
    yaml_path.write_text(
        "id: t\n"
        "turns:\n"
        "  - user: hi\n"
        "    expect:\n"
        "      reply_matches_any:\n"
        '        - "BK-\\\\d+"\n'
        "      reply_matches_all:\n"
        '        - "tomorrow"\n'
    )
    transcript = load_transcript(yaml_path)
    assert transcript.turns[0].expect.reply_matches_any == ["BK-\\d+"]
    assert transcript.turns[0].expect.reply_matches_all == ["tomorrow"]


def test_load_transcript_parses_tool_calls_ordered(tmp_path: Path):
    yaml_path = tmp_path / "ordered.yaml"
    yaml_path.write_text(
        "id: t\n"
        "turns:\n"
        "  - user: hi\n"
        "    expect:\n"
        "      tool_calls_include: [auth, fetch]\n"
        "      tool_calls_ordered: true\n"
    )
    transcript = load_transcript(yaml_path)
    assert transcript.turns[0].expect.tool_calls_ordered is True
    assert load_transcript(SAMPLE).turns[0].expect.tool_calls_ordered is False


def test_load_transcript_parses_tool_calls_args(tmp_path: Path):
    yaml_path = tmp_path / "args.yaml"
    yaml_path.write_text(
        "id: t\n"
        "turns:\n"
        "  - user: hi\n"
        "    expect:\n"
        "      tool_calls_args:\n"
        "        - tool: book_slot\n"
        "          args:\n"
        "            time: 10am\n"
        "          mode: exact\n"
        "        - tool: book_slot\n"
        "          judge:\n"
        "            rubric: Time within business hours\n"
    )
    transcript = load_transcript(yaml_path)
    entries = transcript.turns[0].expect.tool_calls_args
    assert len(entries) == 2
    assert entries[0].tool == "book_slot"
    assert entries[0].args == {"time": "10am"}
    assert entries[0].mode == "exact"
    assert entries[0].judge is None
    assert entries[1].args is None
    assert entries[1].judge.rubric == "Time within business hours"


def test_load_transcript_rejects_tool_calls_args_without_args_or_judge(tmp_path: Path):
    yaml_path = tmp_path / "bad_args.yaml"
    yaml_path.write_text(
        "id: t\nturns:\n  - user: hi\n    expect:\n      tool_calls_args:\n        - tool: book_slot\n"
    )
    with pytest.raises(ValueError, match="needs 'args'"):
        load_transcript(yaml_path)


def test_audio_field_defaults_to_none(tmp_path: Path):
    yaml_path = tmp_path / "no_audio.yaml"
    yaml_path.write_text("id: t\nturns:\n  - user: hi\n")
    transcript = load_transcript(yaml_path)
    assert transcript.turns[0].audio is None


def test_audio_field_resolves_relative_to_yaml_dir(tmp_path: Path):
    yaml_path = tmp_path / "with_audio.yaml"
    yaml_path.write_text("id: t\nturns:\n  - user: hi\n    audio: turn1.wav\n")
    transcript = load_transcript(yaml_path)
    assert transcript.turns[0].audio == tmp_path / "turn1.wav"


def test_audio_field_keeps_absolute_path(tmp_path: Path):
    abs_audio = tmp_path / "elsewhere" / "x.wav"
    yaml_path = tmp_path / "abs.yaml"
    yaml_path.write_text(f"id: t\nturns:\n  - user: hi\n    audio: {abs_audio}\n")
    transcript = load_transcript(yaml_path)
    assert transcript.turns[0].audio == abs_audio


def test_yaml_discovery_and_collection(pytester: pytest.Pytester):
    pytester.makeini("[pytest]\nasyncio_mode = auto\n")
    pytester.makefile(
        ".yaml",
        **{"tests/evals/hello": ("id: hello_test\nthreshold: 0.0\nruns: 1\nturns:\n  - user: hi\n")},
    )
    pytester.makeconftest(
        """
        import pytest

        @pytest.fixture
        def llm_eval_agent():
            async def agent(history):
                return "confirmed", []
            return agent
        """
    )
    result = pytester.runpytest("--agent-eval-live", "--collect-only", "-q")
    result.stdout.fnmatch_lines(["*hello_test*"])


def test_yaml_item_passes_with_matching_agent(pytester: pytest.Pytester):
    pytester.makeini("[pytest]\nasyncio_mode = auto\n")
    pytester.makefile(
        ".yaml",
        **{
            "tests/evals/booking": (
                "id: booking_ok\n"
                "threshold: 1.0\n"
                "runs: 1\n"
                "turns:\n"
                "  - user: book me\n"
                "    expect:\n"
                "      reply_contains_any:\n"
                "        - confirmed\n"
            )
        },
    )
    pytester.makeconftest(
        """
        import pytest

        @pytest.fixture
        def llm_eval_agent():
            async def agent(history):
                return "booking confirmed!", []
            return agent
        """
    )
    result = pytester.runpytest("--agent-eval-live", "-v")
    result.stdout.fnmatch_lines(["*booking_ok*PASSED*"])
    assert result.ret == 0


def test_yaml_item_fails_with_non_matching_agent(pytester: pytest.Pytester):
    pytester.makeini("[pytest]\nasyncio_mode = auto\n")
    pytester.makefile(
        ".yaml",
        **{
            "tests/evals/fail_test": (
                "id: fail_case\n"
                "threshold: 1.0\n"
                "runs: 1\n"
                "turns:\n"
                "  - user: book me\n"
                "    expect:\n"
                "      reply_contains_any:\n"
                "        - confirmed\n"
            )
        },
    )
    pytester.makeconftest(
        """
        import pytest

        @pytest.fixture
        def llm_eval_agent():
            async def agent(history):
                return "error", []
            return agent
        """
    )
    result = pytester.runpytest("--agent-eval-live", "-v")
    result.stdout.fnmatch_lines(["*fail_case*FAILED*"])
    assert result.ret != 0
