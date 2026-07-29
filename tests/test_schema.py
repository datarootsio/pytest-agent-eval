"""The published JSON Schema must stay in lockstep with the loader and dataclasses."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from pytest_agent_eval.models import Expect, JudgeConfig, ToolCallArgsConfig, Transcript, Turn

REPO_ROOT = Path(__file__).parent.parent
SCHEMA_PATH = REPO_ROOT / "docs" / "schema" / "transcript.json"
SCHEMA = json.loads(SCHEMA_PATH.read_text())
VALIDATOR = Draft202012Validator(SCHEMA)


def test_schema_is_itself_valid() -> None:
    Draft202012Validator.check_schema(SCHEMA)


def _yaml_documents() -> list[Path]:
    fixtures = sorted((REPO_ROOT / "tests" / "fixtures").glob("*.yaml"))
    examples = sorted((REPO_ROOT / "examples").glob("**/evals/*.yaml"))
    return fixtures + examples


@pytest.mark.parametrize("path", _yaml_documents(), ids=lambda p: str(p.relative_to(REPO_ROOT)))
def test_shipped_yaml_documents_validate(path: Path) -> None:
    data = yaml.safe_load(path.read_text())
    VALIDATOR.validate(data)


def test_schema_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        VALIDATOR.validate({"id": "t", "turns": [{"user": "hi"}], "thresold": 0.8})


def test_schema_rejects_missing_required() -> None:
    with pytest.raises(ValidationError):
        VALIDATOR.validate({"turns": [{"user": "hi"}]})
    with pytest.raises(ValidationError):
        VALIDATOR.validate({"id": "t", "turns": [{"expect": {}}]})


def test_schema_rejects_bad_types() -> None:
    with pytest.raises(ValidationError):
        VALIDATOR.validate({"id": "t", "threshold": "high", "turns": [{"user": "hi"}]})
    with pytest.raises(ValidationError):
        VALIDATOR.validate({"id": "t", "turns": [{"user": "hi", "expect": {"reply_contains_any": "scalar"}}]})


def test_schema_rejects_empty_turns() -> None:
    with pytest.raises(ValidationError):
        VALIDATOR.validate({"id": "t", "turns": []})


def test_schema_rejects_tool_calls_args_without_args_or_judge() -> None:
    with pytest.raises(ValidationError):
        VALIDATOR.validate({"id": "t", "turns": [{"user": "hi", "expect": {"tool_calls_args": [{"tool": "x"}]}}]})


def _model_field_names(cls: type) -> set[str]:
    return {name for name, f in cls.model_fields.items() if not f.exclude}


def test_published_schema_matches_the_models() -> None:
    """The shipped schema and the models must agree field-for-field.

    The models are now the single source of truth — the loader's hand-maintained
    frozensets are gone — so this checks the *published artifact* has not drifted from
    them. Editors point at that file, so it can be stale in a way the models cannot.
    """
    assert set(SCHEMA["properties"]) == _model_field_names(Transcript)
    assert set(SCHEMA["$defs"]["turn"]["properties"]) == _model_field_names(Turn)
    assert set(SCHEMA["$defs"]["expect"]["properties"]) == _model_field_names(Expect)
    assert set(SCHEMA["$defs"]["judge"]["properties"]) == _model_field_names(JudgeConfig)
    assert set(SCHEMA["$defs"]["toolCallArgs"]["properties"]) == _model_field_names(ToolCallArgsConfig)


def test_evaluators_is_excluded_from_the_schema() -> None:
    """It holds arbitrary Python objects, which have no JSON representation."""
    assert "evaluators" in Expect.model_fields
    assert "evaluators" not in _model_field_names(Expect)
    generated = Transcript.model_json_schema()
    assert "evaluators" not in generated["$defs"]["Expect"]["properties"]


def test_generated_schema_keeps_audio_a_string() -> None:
    """A bare Path field would emit {"format": "path"}, which editors flag on valid YAML."""
    generated = Transcript.model_json_schema()
    turn = generated["$defs"]["Turn"]["properties"]["audio"]
    assert json.dumps(turn).count("path") == 0, turn


@pytest.mark.parametrize(
    ("document", "should_pass"),
    [
        ({"id": "t", "turns": [{"user": "hi"}]}, True),
        ({"id": "t", "threshold": 1, "turns": [{"user": "hi"}]}, True),
        ({"id": "t", "runs": 2.0, "turns": [{"user": "hi"}]}, True),
        ({"id": "t", "thresold": 0.8, "turns": [{"user": "hi"}]}, False),
        ({"id": "t", "threshold": "high", "turns": [{"user": "hi"}]}, False),
        ({"id": "t", "turns": []}, False),
        ({"turns": [{"user": "hi"}]}, False),
    ],
    ids=["minimal", "int_threshold", "integral_float_runs", "typo", "bad_type", "no_turns", "no_id"],
)
def test_models_and_published_schema_agree_on_acceptance(document: dict, should_pass: bool) -> None:
    """Two independent validators must not disagree about what a valid transcript is.

    A document the schema accepts but the loader rejects (or vice versa) means a user's
    editor and their test run tell them different things.
    """
    from pytest_agent_eval.yaml_loader import TranscriptError, validate_transcript_dict

    schema_ok = VALIDATOR.is_valid(document)
    try:
        validate_transcript_dict(document)
        loader_ok = True
    except TranscriptError:
        loader_ok = False

    assert schema_ok is should_pass
    assert loader_ok is should_pass
