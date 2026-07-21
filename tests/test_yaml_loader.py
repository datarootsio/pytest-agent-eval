from pathlib import Path

import pytest

from pytest_agent_eval.yaml_loader import TranscriptError, load_transcript, validate_transcript_dict

SAMPLE = Path(__file__).parent / "fixtures" / "sample_transcript.yaml"


def _load(tmp_path: Path, content: str):
    yaml_path = tmp_path / "t.yaml"
    yaml_path.write_text(content)
    return load_transcript(yaml_path)


# --- validation ---


def test_unknown_expect_field_suggests_close_match(tmp_path: Path):
    with pytest.raises(TranscriptError) as excinfo:
        _load(tmp_path, "id: t\nturns:\n  - user: hi\n    expect:\n      tool_call_include: [x]\n")
    message = str(excinfo.value)
    assert "turns[0].expect" in message
    assert "Did you mean 'tool_calls_include'?" in message
    assert "Valid fields" in message
    assert "schema/transcript.json" in message


def test_unknown_top_level_field_reports_location(tmp_path: Path):
    with pytest.raises(TranscriptError, match="thresold"):
        _load(tmp_path, "id: t\nthresold: 0.8\nturns:\n  - user: hi\n")


def test_missing_id_is_didactic(tmp_path: Path):
    with pytest.raises(TranscriptError, match="missing required field 'id'"):
        _load(tmp_path, "turns:\n  - user: hi\n")


def test_missing_user_reports_turn_index(tmp_path: Path):
    with pytest.raises(TranscriptError, match=r"turns\[1\].*missing required field 'user'"):
        _load(tmp_path, "id: t\nturns:\n  - user: hi\n  - expect:\n      reply_contains_any: [x]\n")


def test_missing_rubric_in_judge(tmp_path: Path):
    with pytest.raises(TranscriptError, match=r"turns\[0\].expect.judge.*rubric"):
        _load(tmp_path, "id: t\nturns:\n  - user: hi\n    expect:\n      judge:\n        model: openai:gpt-4o\n")


def test_scalar_where_list_expected(tmp_path: Path):
    with pytest.raises(TranscriptError, match="must be a list of strings"):
        _load(tmp_path, "id: t\nturns:\n  - user: hi\n    expect:\n      reply_contains_any: confirmed\n")


def test_threshold_out_of_range(tmp_path: Path):
    with pytest.raises(TranscriptError, match="between 0 and 1"):
        _load(tmp_path, "id: t\nthreshold: 1.5\nturns:\n  - user: hi\n")


def test_runs_must_be_positive_int(tmp_path: Path):
    with pytest.raises(TranscriptError, match="integer >= 1"):
        _load(tmp_path, "id: t\nruns: 0\nturns:\n  - user: hi\n")


def test_empty_turns_is_an_error(tmp_path: Path):
    """Behavior change: an empty transcript used to collect and vacuously PASS."""
    with pytest.raises(TranscriptError, match="at least one turn"):
        _load(tmp_path, "id: t\nturns: []\n")
    with pytest.raises(TranscriptError, match="at least one turn"):
        _load(tmp_path, "id: t\n")


def test_invalid_regex_pattern_fails_validation_with_location(tmp_path: Path):
    with pytest.raises(TranscriptError, match=r"turns\[0\].expect.reply_matches_any\[0\].*invalid regex"):
        _load(tmp_path, 'id: t\nturns:\n  - user: hi\n    expect:\n      reply_matches_any: ["("]\n')


def test_runs_accepts_integral_float(tmp_path: Path):
    transcript = _load(tmp_path, "id: t\nruns: 2.0\nturns:\n  - user: hi\n")
    assert transcript.runs == 2
    assert isinstance(transcript.runs, int)
    with pytest.raises(TranscriptError, match="integer >= 1"):
        _load(tmp_path, "id: t\nruns: 2.5\nturns:\n  - user: hi\n")


def test_load_transcript_honours_config_defaults(tmp_path: Path):
    yaml_path = tmp_path / "t.yaml"
    yaml_path.write_text("id: t\nturns:\n  - user: hi\n")
    transcript = load_transcript(yaml_path, default_threshold=0.5, default_runs=4)
    assert transcript.threshold == 0.5
    assert transcript.runs == 4

    explicit = tmp_path / "explicit.yaml"
    explicit.write_text("id: t2\nthreshold: 0.9\nruns: 2\nturns:\n  - user: hi\n")
    transcript = load_transcript(explicit, default_threshold=0.5, default_runs=4)
    assert transcript.threshold == 0.9
    assert transcript.runs == 2


def test_yaml_syntax_error_shows_clean_collect_error(pytester: pytest.Pytester):
    pytester.makeini("[pytest]\nasyncio_mode = auto\n")
    pytester.makefile(
        ".yaml",
        **{"tests/evals/broken_syntax": ("id: broken\nturns:\n  - user: hi\n   expect:\n      judge: x\n")},
    )
    pytester.makeconftest(
        """
        import pytest

        @pytest.fixture
        def llm_eval_agent():
            async def agent(history):
                return "ok", []
            return agent
        """
    )
    result = pytester.runpytest("--agent-eval-live")
    assert result.ret != 0
    result.stdout.fnmatch_lines(["*invalid YAML at line*"])
    assert "yaml.parser" not in result.stdout.str()


def test_yaml_transcript_defaults_come_from_config(pytester: pytest.Pytester):
    pytester.makepyprojecttoml(
        """
        [tool.agent_eval]
        yaml_dirs = ["tests/evals"]
        threshold = 0.0
        """
    )
    pytester.makeini("[pytest]\nasyncio_mode = auto\n")
    pytester.makefile(
        ".yaml",
        **{
            "tests/evals/no_threshold": (
                "id: config_default\nturns:\n  - user: hi\n    expect:\n      reply_contains_any: [impossible]\n"
            )
        },
    )
    pytester.makeconftest(
        """
        import pytest

        @pytest.fixture
        def llm_eval_agent():
            async def agent(history):
                return "nope", []
            return agent
        """
    )
    result = pytester.runpytest("--agent-eval-live", "-v")
    result.stdout.fnmatch_lines(["*config_default*PASSED*"])
    assert result.ret == 0


def test_validate_transcript_dict_rejects_non_mapping():
    with pytest.raises(TranscriptError, match="must be a YAML mapping"):
        validate_transcript_dict(["not", "a", "dict"], source="x.yaml")


def test_invalid_yaml_shows_clean_collect_error(pytester: pytest.Pytester):
    pytester.makeini("[pytest]\nasyncio_mode = auto\n")
    pytester.makefile(
        ".yaml",
        **{"tests/evals/broken": ("id: broken\nturns:\n  - user: hi\n    expect:\n      reply_contain_any: [x]\n")},
    )
    pytester.makeconftest(
        """
        import pytest

        @pytest.fixture
        def llm_eval_agent():
            async def agent(history):
                return "ok", []
            return agent
        """
    )
    result = pytester.runpytest("--agent-eval-live")
    assert result.ret != 0
    result.stdout.fnmatch_lines(["*Did you mean 'reply_contains_any'?*"])


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
