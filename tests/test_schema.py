"""The published JSON Schema must stay in lockstep with the loader and dataclasses."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from pytest_agent_eval.models import Expect, JudgeConfig, ToolCallArgsConfig, Transcript, Turn
from pytest_agent_eval.yaml_loader import (
    EXPECT_FIELDS,
    JUDGE_FIELDS,
    TOOL_CALLS_ARGS_FIELDS,
    TOP_LEVEL_FIELDS,
    TURN_FIELDS,
)

REPO_ROOT = Path(__file__).parent.parent
SCHEMA_PATH = REPO_ROOT / "docs" / "schema" / "transcript.json"
SCHEMA = json.loads(SCHEMA_PATH.read_text())
VALIDATOR = Draft202012Validator(SCHEMA)


def test_schema_is_itself_valid():
    Draft202012Validator.check_schema(SCHEMA)


def _yaml_documents() -> list[Path]:
    fixtures = sorted((REPO_ROOT / "tests" / "fixtures").glob("*.yaml"))
    examples = sorted((REPO_ROOT / "examples").glob("**/evals/*.yaml"))
    return fixtures + examples


@pytest.mark.parametrize("path", _yaml_documents(), ids=lambda p: str(p.relative_to(REPO_ROOT)))
def test_shipped_yaml_documents_validate(path: Path):
    data = yaml.safe_load(path.read_text())
    VALIDATOR.validate(data)


def test_schema_rejects_unknown_field():
    with pytest.raises(ValidationError):
        VALIDATOR.validate({"id": "t", "turns": [{"user": "hi"}], "thresold": 0.8})


def test_schema_rejects_missing_required():
    with pytest.raises(ValidationError):
        VALIDATOR.validate({"turns": [{"user": "hi"}]})
    with pytest.raises(ValidationError):
        VALIDATOR.validate({"id": "t", "turns": [{"expect": {}}]})


def test_schema_rejects_bad_types():
    with pytest.raises(ValidationError):
        VALIDATOR.validate({"id": "t", "threshold": "high", "turns": [{"user": "hi"}]})
    with pytest.raises(ValidationError):
        VALIDATOR.validate({"id": "t", "turns": [{"user": "hi", "expect": {"reply_contains_any": "scalar"}}]})


def test_schema_rejects_empty_turns():
    with pytest.raises(ValidationError):
        VALIDATOR.validate({"id": "t", "turns": []})


def test_schema_rejects_tool_calls_args_without_args_or_judge():
    with pytest.raises(ValidationError):
        VALIDATOR.validate({"id": "t", "turns": [{"user": "hi", "expect": {"tool_calls_args": [{"tool": "x"}]}}]})


def _dataclass_field_names(cls: type) -> set[str]:
    return {f.name for f in dataclasses.fields(cls) if f.init}


def test_three_way_parity_schema_loader_dataclasses():
    """Schema properties == loader known-field sets == dataclass fields (modulo Python-only fields)."""
    schema_top = set(SCHEMA["properties"])
    schema_turn = set(SCHEMA["$defs"]["turn"]["properties"])
    schema_expect = set(SCHEMA["$defs"]["expect"]["properties"])
    schema_judge = set(SCHEMA["$defs"]["judge"]["properties"])
    schema_args = set(SCHEMA["$defs"]["toolCallArgs"]["properties"])

    assert schema_top == set(TOP_LEVEL_FIELDS) == _dataclass_field_names(Transcript)
    assert schema_turn == set(TURN_FIELDS) == _dataclass_field_names(Turn)
    assert schema_expect == set(EXPECT_FIELDS) == _dataclass_field_names(Expect) - {"evaluators"}
    assert schema_judge == set(JUDGE_FIELDS) == _dataclass_field_names(JudgeConfig)
    assert schema_args == set(TOOL_CALLS_ARGS_FIELDS) == _dataclass_field_names(ToolCallArgsConfig)
