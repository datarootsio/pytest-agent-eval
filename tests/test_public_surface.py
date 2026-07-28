"""Machine-checked invariants on the public data layer.

These turn the refactor's rules into tests, so a regression is a test failure rather
than something a reviewer has to notice.
"""

from __future__ import annotations

import dataclasses
import inspect
import re
import typing

import pytest

import pytest_agent_eval
from pytest_agent_eval import models

# Records the plugin produces and hands out. Freezing these is what makes them safe to
# pass around, cache and compare.
FROZEN_RECORDS = [
    models.EvalResult,
    models.Message,
    models.TurnContext,
    models.TurnResult,
    models.RunResult,
    models.TranscriptResult,
]

# Types a *user* constructs and may reasonably want to build up field by field. These
# stay mutable on purpose; freezing them would be a breaking change for no benefit.
MUTABLE_CONFIG = [
    models.Turn,
    models.Transcript,
    models.Expect,
    models.JudgeConfig,
    models.ToolCallArgsConfig,
]


@pytest.mark.parametrize("record", FROZEN_RECORDS, ids=lambda c: c.__name__)
def test_public_records_are_frozen_and_slotted(record: type) -> None:
    params = record.__dataclass_params__
    assert params.frozen, f"{record.__name__} must be frozen"
    assert getattr(record, "__slots__", None) is not None, f"{record.__name__} must declare __slots__"


@pytest.mark.parametrize("config", MUTABLE_CONFIG, ids=lambda c: c.__name__)
def test_user_constructed_config_stays_mutable(config: type) -> None:
    """Documented as a deliberate asymmetry, not an oversight.

    These are pydantic models (they parse external documents); the check is that
    validation did not also make them read-only.
    """
    assert not config.model_config.get("frozen", False)


def test_no_dataclass_hides_attributes_from_its_field_list() -> None:
    """An attribute set in __post_init__ but not declared is invisible and blocks slots."""
    for name in dir(models):
        obj = getattr(models, name)
        if not (inspect.isclass(obj) and dataclasses.is_dataclass(obj)):
            continue
        declared = {f.name for f in dataclasses.fields(obj)}
        slots = getattr(obj, "__slots__", ())
        assert set(slots) <= declared, f"{name} has slots outside its field list: {set(slots) - declared}"


# Signatures whose tuple/dict shape is mandated from outside and cannot be a record.
_SHAPE_ALLOWLIST = {
    # pytest requires exactly (fspath, lineno, domain).
    "AgentEvalItem.reportinfo",
    # A NamedTuple *is* the record here; it is a tuple by design for back-compat.
    "AgentReply",
}


def test_no_public_signature_returns_a_bare_tuple_or_dict() -> None:
    """A dict is a serialisation format and a tuple is not a record type."""
    offenders: list[str] = []
    for name in pytest_agent_eval.__all__:
        obj = getattr(pytest_agent_eval, name)
        if name in _SHAPE_ALLOWLIST or not callable(obj):
            continue
        for member_name, member in _public_callables(obj):
            try:
                annotation = str(typing.get_type_hints(member).get("return", ""))
            except (NameError, TypeError):  # pragma: no cover - unresolvable forward ref
                continue
            if any(bad in annotation for bad in ("tuple[", "dict[")) and "to_dict" not in member_name:
                offenders.append(f"{name}.{member_name} -> {annotation}")
    assert offenders == [], f"anonymous structural returns on the public API: {offenders}"


def _public_callables(obj: object) -> list[tuple[str, object]]:
    if not inspect.isclass(obj):
        return [("", obj)]
    return [
        (n, m)
        for n, m in inspect.getmembers(obj, callable)
        if not n.startswith("_") and (getattr(m, "__module__", None) or "").startswith("pytest_agent_eval")
    ]


# Every remaining explicit Any in src/, enumerated. This set only ever shrinks; adding
# to it is a visible one-line diff, which is stronger than a checker directive a
# `# type: ignore` could silence.
ANY_ALLOWLIST = {
    "yaml_loader.py": "pytest passthrough: **kwargs to pytest.Item, and self.funcargs",
    "plugin.py": "pytest passthrough: terminalreporter",
}


def test_any_is_confined_to_the_allowlist() -> None:
    """`Any` silently disables checking, so every remaining use is named."""
    from pathlib import Path

    src = Path(__file__).parent.parent / "src" / "pytest_agent_eval"
    unexpected: list[str] = []
    for path in sorted(src.rglob("*.py")):
        rel = str(path.relative_to(src))
        uses_any = any(
            re.search(r"\bAny\b", line) and not line.lstrip().startswith("#") for line in path.read_text().splitlines()
        )
        if uses_any and rel not in ANY_ALLOWLIST:
            unexpected.append(rel)
    assert unexpected == [], f"new Any outside the allowlist: {unexpected}"
