"""Tests for normalisation of framework-specific tool-call arguments."""

from pytest_agent_eval.adapters._args import coerce_args


def test_coerce_args_passes_dict_through():
    assert coerce_args({"a": 1}) == {"a": 1}


def test_coerce_args_parses_json_string():
    assert coerce_args('{"date": "tomorrow"}') == {"date": "tomorrow"}


def test_coerce_args_returns_none_for_invalid_json():
    assert coerce_args("{not json") is None


def test_coerce_args_returns_none_for_non_dict_json():
    assert coerce_args("[1, 2]") is None


def test_coerce_args_returns_none_for_other_types():
    assert coerce_args(None) is None
    assert coerce_args(42) is None
