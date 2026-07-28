"""Direct tests for the pydantic -> TranscriptError translation layer.

The table-driven tests in test_yaml_loader.py cover every message a real transcript can
produce. These cover the layer's own defensive paths: what it does with an error type it
has no bespoke phrasing for, and how it walks the model tree to suggest field names.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from pytest_agent_eval._errors import (
    SCHEMA_URL,
    TranscriptError,
    _fields_at,
    _model_of,
    as_transcript_error,
)
from pytest_agent_eval.models import Expect, JudgeConfig, Transcript, Turn


def _error(model: type[BaseModel], document: object) -> ValidationError:
    with pytest.raises(ValidationError) as excinfo:
        model.model_validate(document)
    return excinfo.value


def test_every_message_links_the_schema() -> None:
    """The reference is what turns a rejection into something a user can act on."""
    err = as_transcript_error(_error(Transcript, {"turns": [{"user": "hi"}]}), "t.yaml", Transcript)
    assert err.args[0].endswith(f"Schema reference: {SCHEMA_URL}")
    assert isinstance(err, TranscriptError)
    assert isinstance(err, ValueError), "callers catch ValueError"


def test_unmapped_error_types_still_produce_a_located_message() -> None:
    """A future pydantic error type must degrade to something readable, not a KeyError."""

    class Odd(BaseModel):
        value: bytes

    err = as_transcript_error(_error(Odd, {"value": 123}), "t.yaml", Odd)
    message = err.args[0]
    assert message.startswith("t.yaml.value: ")
    assert "123" in message


def test_non_evaluator_objects_are_rejected_with_a_useful_message() -> None:
    """Expect.evaluators isinstance-checks against the Evaluator protocol."""

    class NotAnEvaluator:
        pass

    err = as_transcript_error(_error(Expect, {"evaluators": [NotAnEvaluator()]}), "t.yaml", Expect)
    assert "must be an evaluator with an async 'evaluate(ctx)' method" in err.args[0]
    assert "NotAnEvaluator" in err.args[0]


def test_real_evaluators_are_accepted() -> None:
    from pytest_agent_eval.evaluators.contains import ContainsEvaluator

    assert Expect(evaluators=[ContainsEvaluator(any_of=["x"])]).evaluators


# --- model-tree walking, which backs the "Did you mean?" suggestions ---


def test_model_of_looks_through_lists_and_unions() -> None:
    assert _model_of(Turn) is Turn
    assert _model_of(list[Turn]) is Turn
    assert _model_of(JudgeConfig | None) is JudgeConfig
    assert _model_of(str) is None
    assert _model_of(list[str]) is None


def test_fields_at_walks_to_the_rejecting_container() -> None:
    assert set(_fields_at(Transcript, ("thresold",))) == set(Transcript.model_fields)
    assert set(_fields_at(Transcript, ("turns", 0, "usr"))) == set(Turn.model_fields)
    assert set(_fields_at(Transcript, ("turns", 0, "expect", "judge", "modle"))) == set(JudgeConfig.model_fields)


def test_fields_at_stops_at_a_non_model_field() -> None:
    """A loc pointing through a scalar cannot be walked further; suggest what we reached."""
    assert set(_fields_at(Transcript, ("turns", 0, "user", "deeper"))) == set(Turn.model_fields)


def test_fields_at_omits_excluded_fields_from_suggestions() -> None:
    """Evaluators is Python-only, so suggesting it for a YAML typo would mislead."""
    assert "evaluators" not in _fields_at(Transcript, ("turns", 0, "expect", "judge"))
    assert "evaluators" not in _fields_at(Expect, ("nope",))
