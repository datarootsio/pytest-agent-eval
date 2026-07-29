from pathlib import Path

import pytest

from pytest_agent_eval.models import Transcript
from pytest_agent_eval.yaml_loader import TranscriptError, load_transcript, validate_transcript_dict
from tests.helpers.pytester_project import EvalProject, raising_agent, static_agent

SAMPLE = Path(__file__).parent / "fixtures" / "sample_transcript.yaml"

_CONFIRMED_TRANSCRIPT = (
    "id: {id}\nthreshold: 1.0\nruns: 1\nturns:\n"
    "  - user: book me\n    expect:\n      reply_contains_any:\n        - confirmed\n"
)


def _load(tmp_path: Path, content: str):
    yaml_path = tmp_path / "t.yaml"
    yaml_path.write_text(content)
    return load_transcript(yaml_path)


# --- the didactic-error surface, exhaustively ---
#
# Every rejection the loader can produce, as (case_id, yaml, expected fragments).
# Each fragment is a substring that must appear in the message; together they pin
# the location prefix and the didactic phrasing users actually read. This table is
# the contract that any reimplementation of the validation layer must satisfy.

_REJECTED: list[tuple[str, str, list[str]]] = [
    # top level
    ("top_not_mapping", "- not\n- a\n- mapping\n", ["must be a YAML mapping with 'id' and 'turns' keys"]),
    (
        "top_unknown_field",
        "id: t\nthresold: 0.8\nturns:\n  - user: hi\n",
        ["unknown field 'thresold'", "Did you mean 'threshold'?", "Valid fields"],
    ),
    ("top_unknown_no_match", "id: t\nzzzzzz: 1\nturns:\n  - user: hi\n", ["unknown field 'zzzzzz'", "Valid fields"]),
    ("missing_id", "turns:\n  - user: hi\n", ["missing required field 'id'"]),
    ("id_not_string", "id: 123\nturns:\n  - user: hi\n", [".id", "must be a string"]),
    # threshold
    (
        "threshold_string",
        "id: t\nthreshold: high\nturns:\n  - user: hi\n",
        [".threshold", "must be a number between 0 and 1"],
    ),
    (
        "threshold_bool",
        "id: t\nthreshold: true\nturns:\n  - user: hi\n",
        [".threshold", "must be a number between 0 and 1"],
    ),
    (
        "threshold_numeric_string",
        "id: t\nthreshold: '0.5'\nturns:\n  - user: hi\n",
        [".threshold", "must be a number between 0 and 1"],
    ),
    (
        "threshold_too_high",
        "id: t\nthreshold: 1.5\nturns:\n  - user: hi\n",
        [".threshold", "must be a number between 0 and 1"],
    ),
    (
        "threshold_negative",
        "id: t\nthreshold: -0.1\nturns:\n  - user: hi\n",
        [".threshold", "must be a number between 0 and 1"],
    ),
    # runs
    ("runs_zero", "id: t\nruns: 0\nturns:\n  - user: hi\n", [".runs", "must be an integer >= 1"]),
    ("runs_fractional", "id: t\nruns: 2.5\nturns:\n  - user: hi\n", [".runs", "must be an integer >= 1"]),
    ("runs_bool", "id: t\nruns: true\nturns:\n  - user: hi\n", [".runs", "must be an integer >= 1"]),
    ("runs_string", "id: t\nruns: many\nturns:\n  - user: hi\n", [".runs", "must be an integer >= 1"]),
    # tags
    (
        "tags_scalar",
        "id: t\ntags: one\nturns:\n  - user: hi\n",
        [".tags", "must be a list of strings", "YAML lists look like"],
    ),
    ("tags_list_of_int", "id: t\ntags: [1, 2]\nturns:\n  - user: hi\n", [".tags", "must be a list of strings"]),
    # turns
    ("turns_empty", "id: t\nturns: []\n", ["must define at least one turn"]),
    ("turns_absent", "id: t\n", ["must define at least one turn"]),
    ("turns_scalar", "id: t\nturns: nope\n", [".turns", "must be a list of turns"]),
    ("turn_not_mapping", "id: t\nturns:\n  - just a string\n", ["turns[0]", "must be a mapping with a 'user' key"]),
    (
        "turn_unknown_field",
        "id: t\nturns:\n  - user: hi\n    usr: oops\n",
        ["turns[0]", "unknown field 'usr'", "Did you mean 'user'?"],
    ),
    (
        "turn_missing_user",
        "id: t\nturns:\n  - user: hi\n  - expect:\n      reply_contains_any: [x]\n",
        ["turns[1]", "missing required field 'user'"],
    ),
    ("turn_user_not_string", "id: t\nturns:\n  - user: 42\n", ["turns[0].user", "must be a string"]),
    (
        "turn_audio_not_string",
        "id: t\nturns:\n  - user: hi\n    audio: 42\n",
        ["turns[0].audio", "must be a WAV path string"],
    ),
    # expect
    (
        "expect_not_mapping",
        "id: t\nturns:\n  - user: hi\n    expect: nope\n",
        ["turns[0].expect", "must be a mapping of expectations"],
    ),
    (
        "expect_unknown_field",
        "id: t\nturns:\n  - user: hi\n    expect:\n      tool_call_include: [x]\n",
        ["turns[0].expect", "unknown field 'tool_call_include'", "Did you mean 'tool_calls_include'?"],
    ),
    (
        "expect_scalar_where_list",
        "id: t\nturns:\n  - user: hi\n    expect:\n      reply_contains_any: confirmed\n",
        ["turns[0].expect.reply_contains_any", "must be a list of strings", "YAML lists look like"],
    ),
    (
        "expect_list_of_int",
        "id: t\nturns:\n  - user: hi\n    expect:\n      reply_contains_all: [1, 2]\n",
        ["turns[0].expect.reply_contains_all", "must be a list of strings"],
    ),
    (
        "expect_bad_regex",
        'id: t\nturns:\n  - user: hi\n    expect:\n      reply_matches_any: ["("]\n',
        ["turns[0].expect.reply_matches_any[0]", "invalid regex pattern"],
    ),
    (
        "expect_bad_regex_all",
        'id: t\nturns:\n  - user: hi\n    expect:\n      reply_matches_all: ["a", "[b"]\n',
        ["turns[0].expect.reply_matches_all[1]", "invalid regex pattern"],
    ),
    (
        "expect_ordered_not_bool",
        "id: t\nturns:\n  - user: hi\n    expect:\n      tool_calls_ordered: yesplease\n",
        ["turns[0].expect.tool_calls_ordered", "must be true or false"],
    ),
    # judge
    (
        "judge_not_mapping",
        "id: t\nturns:\n  - user: hi\n    expect:\n      judge: just-a-string\n",
        ["turns[0].expect.judge", "must be a mapping with a 'rubric' key"],
    ),
    (
        "judge_unknown_field",
        "id: t\nturns:\n  - user: hi\n    expect:\n      judge:\n        rubric: r\n        modle: m\n",
        ["turns[0].expect.judge", "unknown field 'modle'", "Did you mean 'model'?"],
    ),
    (
        "judge_missing_rubric",
        "id: t\nturns:\n  - user: hi\n    expect:\n      judge:\n        model: openai:gpt-4o\n",
        ["turns[0].expect.judge", "missing required field 'rubric'"],
    ),
    (
        "judge_rubric_not_string",
        "id: t\nturns:\n  - user: hi\n    expect:\n      judge:\n        rubric: 42\n",
        ["turns[0].expect.judge.rubric", "must be a string"],
    ),
    (
        "judge_model_not_string",
        "id: t\nturns:\n  - user: hi\n    expect:\n      judge:\n        rubric: r\n        model: 42\n",
        ["turns[0].expect.judge.model", "must be a string like 'openai:gpt-4o'"],
    ),
    # tool_calls_args
    (
        "tca_not_list",
        "id: t\nturns:\n  - user: hi\n    expect:\n      tool_calls_args: nope\n",
        ["turns[0].expect.tool_calls_args", "must be a list of tool-argument assertions"],
    ),
    (
        "tca_entry_not_mapping",
        "id: t\nturns:\n  - user: hi\n    expect:\n      tool_calls_args:\n        - scalar\n",
        ["turns[0].expect.tool_calls_args[0]", "must be a mapping with a 'tool' key"],
    ),
    (
        "tca_unknown_field",
        "id: t\nturns:\n  - user: hi\n    expect:\n      tool_calls_args:\n        - tool: b\n          arg: {}\n",
        ["turns[0].expect.tool_calls_args[0]", "unknown field 'arg'", "Did you mean 'args'?"],
    ),
    (
        "tca_missing_tool",
        "id: t\nturns:\n  - user: hi\n    expect:\n      tool_calls_args:\n        - args:\n            a: 1\n",
        ["turns[0].expect.tool_calls_args[0]", "requires a 'tool' field"],
    ),
    (
        "tca_tool_not_string",
        "id: t\nturns:\n  - user: hi\n    expect:\n      tool_calls_args:\n"
        "        - tool: 42\n          args:\n            a: 1\n",
        ["turns[0].expect.tool_calls_args[0]", "requires a 'tool' field"],
    ),
    (
        "tca_neither_args_nor_judge",
        "id: t\nturns:\n  - user: hi\n    expect:\n      tool_calls_args:\n        - tool: book_slot\n",
        ["turns[0].expect.tool_calls_args[0]", "needs 'args'", "got neither"],
    ),
    (
        "tca_args_not_mapping",
        "id: t\nturns:\n  - user: hi\n    expect:\n      tool_calls_args:\n        - tool: b\n          args: nope\n",
        ["turns[0].expect.tool_calls_args[0].args", "must be a mapping of expected arguments"],
    ),
    (
        "tca_bad_mode",
        "id: t\nturns:\n  - user: hi\n    expect:\n      tool_calls_args:\n"
        "        - tool: b\n          args:\n            a: 1\n          mode: fuzzy\n",
        ["turns[0].expect.tool_calls_args[0].mode", "must be 'subset' or 'exact'"],
    ),
    (
        "tca_nested_judge_missing_rubric",
        "id: t\nturns:\n  - user: hi\n    expect:\n      tool_calls_args:\n"
        "        - tool: b\n          judge:\n            model: openai:gpt-4o\n",
        ["turns[0].expect.tool_calls_args[0].judge", "missing required field 'rubric'"],
    ),
    # deep location reporting
    (
        "deep_location_turn_two",
        "id: t\nturns:\n  - user: hi\n  - user: again\n    expect:\n      judge:\n        rubrik: oops\n",
        ["turns[1].expect.judge", "unknown field 'rubrik'", "Did you mean 'rubric'?"],
    ),
]


@pytest.mark.parametrize(
    ("yaml_source", "fragments"), [(y, f) for _, y, f in _REJECTED], ids=[c for c, _, _ in _REJECTED]
)
def test_malformed_transcript_is_rejected_didactically(tmp_path: Path, yaml_source: str, fragments: list[str]) -> None:
    """Every rejection names its location, explains the fix, and links the schema."""
    with pytest.raises(ValueError) as excinfo:
        _load(tmp_path, yaml_source)
    message = str(excinfo.value)
    for fragment in fragments:
        assert fragment in message, f"{fragment!r} missing from:\n{message}"


_ACCEPTED: list[tuple[str, str]] = [
    ("minimal", "id: t\nturns:\n  - user: hi\n"),
    ("runs_integral_float", "id: t\nruns: 2.0\nturns:\n  - user: hi\n"),
    ("threshold_int_one", "id: t\nthreshold: 1\nturns:\n  - user: hi\n"),
    ("threshold_int_zero", "id: t\nthreshold: 0\nturns:\n  - user: hi\n"),
    ("empty_expect", "id: t\nturns:\n  - user: hi\n    expect: {}\n"),
    ("tags_ok", "id: t\ntags: [gate:a, gate:b]\nturns:\n  - user: hi\n"),
]


@pytest.mark.parametrize("yaml_source", [y for _, y in _ACCEPTED], ids=[c for c, _ in _ACCEPTED])
def test_permissive_documents_keep_parsing(tmp_path: Path, yaml_source: str) -> None:
    """Guards the deliberately lenient cases against a stricter reimplementation."""
    assert _load(tmp_path, yaml_source).turns


# --- validation ---


def test_unknown_expect_field_suggests_close_match(tmp_path: Path) -> None:
    with pytest.raises(TranscriptError) as excinfo:
        _load(tmp_path, "id: t\nturns:\n  - user: hi\n    expect:\n      tool_call_include: [x]\n")
    message = str(excinfo.value)
    assert "turns[0].expect" in message
    assert "Did you mean 'tool_calls_include'?" in message
    assert "Valid fields" in message
    assert "schema/transcript.json" in message


def test_unknown_top_level_field_reports_location(tmp_path: Path) -> None:
    with pytest.raises(TranscriptError, match="thresold"):
        _load(tmp_path, "id: t\nthresold: 0.8\nturns:\n  - user: hi\n")


def test_missing_id_is_didactic(tmp_path: Path) -> None:
    with pytest.raises(TranscriptError, match="missing required field 'id'"):
        _load(tmp_path, "turns:\n  - user: hi\n")


def test_missing_user_reports_turn_index(tmp_path: Path) -> None:
    with pytest.raises(TranscriptError, match=r"turns\[1\].*missing required field 'user'"):
        _load(tmp_path, "id: t\nturns:\n  - user: hi\n  - expect:\n      reply_contains_any: [x]\n")


def test_missing_rubric_in_judge(tmp_path: Path) -> None:
    with pytest.raises(TranscriptError, match=r"turns\[0\].expect.judge.*rubric"):
        _load(tmp_path, "id: t\nturns:\n  - user: hi\n    expect:\n      judge:\n        model: openai:gpt-4o\n")


def test_scalar_where_list_expected(tmp_path: Path) -> None:
    with pytest.raises(TranscriptError, match="must be a list of strings"):
        _load(tmp_path, "id: t\nturns:\n  - user: hi\n    expect:\n      reply_contains_any: confirmed\n")


def test_threshold_out_of_range(tmp_path: Path) -> None:
    with pytest.raises(TranscriptError, match="between 0 and 1"):
        _load(tmp_path, "id: t\nthreshold: 1.5\nturns:\n  - user: hi\n")


def test_runs_must_be_positive_int(tmp_path: Path) -> None:
    with pytest.raises(TranscriptError, match="integer >= 1"):
        _load(tmp_path, "id: t\nruns: 0\nturns:\n  - user: hi\n")


def test_empty_turns_is_an_error(tmp_path: Path) -> None:
    """Behavior change: an empty transcript used to collect and vacuously PASS."""
    with pytest.raises(TranscriptError, match="at least one turn"):
        _load(tmp_path, "id: t\nturns: []\n")
    with pytest.raises(TranscriptError, match="at least one turn"):
        _load(tmp_path, "id: t\n")


def test_invalid_regex_pattern_fails_validation_with_location(tmp_path: Path) -> None:
    with pytest.raises(TranscriptError, match=r"turns\[0\].expect.reply_matches_any\[0\].*invalid regex"):
        _load(tmp_path, 'id: t\nturns:\n  - user: hi\n    expect:\n      reply_matches_any: ["("]\n')


def test_runs_accepts_integral_float(tmp_path: Path) -> None:
    transcript = _load(tmp_path, "id: t\nruns: 2.0\nturns:\n  - user: hi\n")
    assert transcript.runs == 2
    assert isinstance(transcript.runs, int)
    with pytest.raises(TranscriptError, match="integer >= 1"):
        _load(tmp_path, "id: t\nruns: 2.5\nturns:\n  - user: hi\n")


def test_load_transcript_honours_config_defaults(tmp_path: Path) -> None:
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


def test_yaml_syntax_error_shows_clean_collect_error(pytester: pytest.Pytester) -> None:
    EvalProject(
        conftest=static_agent(),
        transcripts={"tests/evals/broken_syntax": "id: broken\nturns:\n  - user: hi\n   expect:\n      judge: x\n"},
    ).write(pytester)
    result = pytester.runpytest("--agent-eval-live")
    assert result.ret != 0
    result.stdout.fnmatch_lines(["*invalid YAML at line*"])
    assert "yaml.parser" not in result.stdout.str()


def test_yaml_transcript_defaults_come_from_config(pytester: pytest.Pytester) -> None:
    pytester.makepyprojecttoml(
        """
        [tool.agent_eval]
        yaml_dirs = ["tests/evals"]
        threshold = 0.0
        """
    )
    EvalProject(
        conftest=static_agent("nope"),
        transcripts={
            "tests/evals/no_threshold": (
                "id: config_default\nturns:\n  - user: hi\n    expect:\n      reply_contains_any: [impossible]\n"
            )
        },
    ).write(pytester)
    result = pytester.runpytest("--agent-eval-live", "-v")
    result.stdout.fnmatch_lines(["*config_default*PASSED*"])
    assert result.ret == 0


def test_validate_transcript_dict_rejects_non_mapping() -> None:
    with pytest.raises(TranscriptError, match="must be a YAML mapping"):
        validate_transcript_dict(["not", "a", "dict"], source="x.yaml")


def test_validate_transcript_dict_returns_the_parsed_transcript() -> None:
    """It returns the Transcript it built rather than throwing it away.

    ``load_transcript`` is now the only caller and it uses that return, so the widening
    from ``-> None`` has to be part of the contract, not an implementation detail.
    """
    transcript = validate_transcript_dict({"id": "t", "threshold": 0.25, "turns": [{"user": "hi"}]})
    assert isinstance(transcript, Transcript)
    assert transcript.id == "t"
    assert transcript.threshold == 0.25
    assert [turn.user for turn in transcript.turns] == ["hi"]


def test_invalid_yaml_shows_clean_collect_error(pytester: pytest.Pytester) -> None:
    EvalProject(
        conftest=static_agent(),
        transcripts={
            "tests/evals/broken": "id: broken\nturns:\n  - user: hi\n    expect:\n      reply_contain_any: [x]\n"
        },
    ).write(pytester)
    result = pytester.runpytest("--agent-eval-live")
    assert result.ret != 0
    result.stdout.fnmatch_lines(["*Did you mean 'reply_contains_any'?*"])


def test_load_transcript_parses_fields() -> None:
    t = load_transcript(SAMPLE)
    assert t.id == "sample_booking"
    assert t.threshold == 1.0
    assert t.runs == 1
    assert t.tags == ["gate:booking"]
    assert len(t.turns) == 1
    assert t.turns[0].user == "Book me a slot"
    assert t.turns[0].expect.reply_contains_any == ["confirmed", "booked"]
    assert t.turns[0].expect.tool_calls_include == ["book_slot"]


def test_load_transcript_parses_regex_expect_fields(tmp_path: Path) -> None:
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


def test_load_transcript_parses_tool_calls_ordered(tmp_path: Path) -> None:
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


def test_load_transcript_parses_tool_calls_args(tmp_path: Path) -> None:
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


def test_load_transcript_rejects_tool_calls_args_without_args_or_judge(tmp_path: Path) -> None:
    yaml_path = tmp_path / "bad_args.yaml"
    yaml_path.write_text(
        "id: t\nturns:\n  - user: hi\n    expect:\n      tool_calls_args:\n        - tool: book_slot\n"
    )
    with pytest.raises(ValueError, match="needs 'args'"):
        load_transcript(yaml_path)


def test_audio_field_defaults_to_none(tmp_path: Path) -> None:
    yaml_path = tmp_path / "no_audio.yaml"
    yaml_path.write_text("id: t\nturns:\n  - user: hi\n")
    transcript = load_transcript(yaml_path)
    assert transcript.turns[0].audio is None


def test_audio_field_resolves_relative_to_yaml_dir(tmp_path: Path) -> None:
    yaml_path = tmp_path / "with_audio.yaml"
    yaml_path.write_text("id: t\nturns:\n  - user: hi\n    audio: turn1.wav\n")
    transcript = load_transcript(yaml_path)
    assert transcript.turns[0].audio == tmp_path / "turn1.wav"


def test_audio_field_keeps_absolute_path(tmp_path: Path) -> None:
    abs_audio = tmp_path / "elsewhere" / "x.wav"
    yaml_path = tmp_path / "abs.yaml"
    yaml_path.write_text(f"id: t\nturns:\n  - user: hi\n    audio: {abs_audio}\n")
    transcript = load_transcript(yaml_path)
    assert transcript.turns[0].audio == abs_audio


def test_yaml_discovery_and_collection(pytester: pytest.Pytester) -> None:
    EvalProject(
        conftest=static_agent("confirmed"),
        transcripts={"tests/evals/hello": "id: hello_test\nthreshold: 0.0\nruns: 1\nturns:\n  - user: hi\n"},
    ).write(pytester)
    result = pytester.runpytest("--agent-eval-live", "--collect-only", "-q")
    result.stdout.fnmatch_lines(["*hello_test*"])


def test_yaml_item_passes_with_matching_agent(pytester: pytest.Pytester) -> None:
    EvalProject(
        conftest=static_agent("booking confirmed!"),
        transcripts={"tests/evals/booking": _CONFIRMED_TRANSCRIPT.format(id="booking_ok")},
    ).write(pytester)
    result = pytester.runpytest("--agent-eval-live", "-v")
    result.stdout.fnmatch_lines(["*booking_ok*PASSED*"])
    assert result.ret == 0


def test_yaml_item_skips_with_didactic_hint_when_agent_fixture_missing(pytester: pytest.Pytester) -> None:
    """A collected transcript with no llm_eval_agent fixture must teach the fix, not error."""
    EvalProject(transcripts={"tests/evals/no_fixture": "id: needs_agent\nturns:\n  - user: hi\n"}).write(pytester)
    # -rs, not -v: the short summary prints the whole skip reason, which -v truncates.
    result = pytester.runpytest("--agent-eval-live", "-rs")
    assert result.ret == 0
    result.assert_outcomes(skipped=1)
    assert "llm_eval_agent fixture not defined" in result.stdout.str()
    assert "INTERNALERROR" not in result.stdout.str()


def test_non_assertion_failure_defers_to_pytest_traceback(pytester: pytest.Pytester) -> None:
    """repr_failure renders threshold assertions plainly but must not swallow real errors."""
    EvalProject(
        conftest=raising_agent("agent exploded"),
        transcripts={"tests/evals/boom": "id: exploding\nturns:\n  - user: hi\n"},
    ).write(pytester)
    result = pytester.runpytest("--agent-eval-live")
    assert result.ret != 0
    result.stdout.fnmatch_lines(["*RuntimeError*agent exploded*"])


def test_yaml_item_fails_with_non_matching_agent(pytester: pytest.Pytester) -> None:
    EvalProject(
        conftest=static_agent("error"),
        transcripts={"tests/evals/fail_test": _CONFIRMED_TRANSCRIPT.format(id="fail_case")},
    ).write(pytester)
    result = pytester.runpytest("--agent-eval-live", "-v")
    result.stdout.fnmatch_lines(["*fail_case*FAILED*"])
    assert result.ret != 0
