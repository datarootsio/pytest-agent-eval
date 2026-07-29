"""Tests for normalisation of framework-specific tool-call arguments."""

from pytest_agent_eval.adapters._args import coerce_args


def test_coerce_args_passes_dict_through() -> None:
    assert coerce_args({"a": 1}) == {"a": 1}


def test_coerce_args_parses_json_string() -> None:
    assert coerce_args('{"date": "tomorrow"}') == {"date": "tomorrow"}


def test_coerce_args_returns_none_for_invalid_json() -> None:
    assert coerce_args("{not json") is None


def test_coerce_args_returns_none_for_non_dict_json() -> None:
    assert coerce_args("[1, 2]") is None


def test_coerce_args_returns_none_for_other_types() -> None:
    # 42 is off-type for the declared signature on purpose. Like the adapters' hasattr
    # guards, the isinstance check is there for callers with no type checker, so a stray
    # scalar out of an untyped SDK must say "not captured" rather than raise.
    assert coerce_args(None) is None
    assert coerce_args(42) is None


def test_coerce_args_stringifies_exotic_keys() -> None:
    """An SDK is free to hand back a non-string key, and dropping the call would be worse.

    ``str(k)`` is why the return annotation is honest rather than asserted: the dict is
    rebuilt key by key. Without this the whole comprehension could be ``dict(raw)``.
    """
    assert coerce_args({1: "a", None: "b"}) == {"1": "a", "None": "b"}


def test_coerce_args_accepts_a_mapping_that_is_not_a_dict() -> None:
    """The signature promises ``Mapping``, so the guard must not narrow to ``dict``.

    A framework is free to hand back its own mapping type, and reporting "not captured"
    for arguments we plainly have would be a lie the signature does not tell.
    """
    from collections.abc import Iterator, Mapping

    class OnlyAMapping(Mapping[str, str]):
        def __getitem__(self, key: str) -> str:
            return {"date": "tomorrow"}[key]

        def __iter__(self) -> Iterator[str]:
            return iter(["date"])

        def __len__(self) -> int:
            return 1

    assert coerce_args(OnlyAMapping()) == {"date": "tomorrow"}
