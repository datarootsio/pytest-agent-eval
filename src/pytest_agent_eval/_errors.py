"""Translate pydantic validation errors into the plugin's didactic transcript errors.

Pydantic's own messages are accurate but terse ("Input should be a valid list"). The
messages here name the location in transcript terms, say what a correct value looks
like, and link the schema — which is the whole reason the hand-rolled validators
existed. This module replaces six of them, so their phrasing lives in one place.
"""

from __future__ import annotations

import difflib
from collections.abc import Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pydantic import BaseModel, ValidationError
    from pydantic_core import ErrorDetails

SCHEMA_URL = "https://datarootsio.github.io/pytest-agent-eval/schema/transcript.json"

Loc = tuple[str | int, ...]

# The didactic tail each of these gets, explaining what the field is *for*. Losing these
# was the main risk in replacing the hand-rolled validators.
_MISSING_HINTS = {
    "id": " (a unique name; it becomes the pytest test name)",
    "user": " (the user message for this turn)",
    "rubric": " (the natural-language criteria for the judge)",
}

# What a list field holds, when it is not a list of plain strings.
_LIST_CONTENTS = {
    "turns": "a list of turns",
    "tool_calls_args": "a list of tool-argument assertions",
}

# What a mapping field must contain, keyed by the field (or its parent, for list items).
_MAPPING_CONTENTS = {
    "judge": "a mapping with a 'rubric' key",
    "expect": "a mapping of expectations",
    "turns": "a mapping with a 'user' key",
    "tool_calls_args": "a mapping with a 'tool' key",
    "args": "a mapping of expected arguments",
}

# pydantic appends the matched union member's name to loc for a union-typed field, so
# Turn.audio (str | Path) reports ('turns', 0, 'audio', 'str'). That tail is not a field.
_UNION_TAGS = frozenset({"str", "int", "float", "bool", "path", "Path", "none", "NoneType"})

# Errors whose message describes the *container* rather than the named field, matching
# where the hand-rolled validators raised from.
_CONTAINER_LOCATED = frozenset({"extra_forbidden", "missing", "too_short"})

_LIST_OF_STR = "must be a list of strings, got {type} ({value!r}). YAML lists look like:\n  {field}:\n    - first item\n    - second item"


class TranscriptError(ValueError):
    """A YAML transcript failed validation, with a didactic location-aware message."""


def fail(location: str, message: str) -> TranscriptError:
    """Build a TranscriptError with a location prefix and a schema reference."""
    return TranscriptError(f"{location}: {message}\nSchema reference: {SCHEMA_URL}")


def as_transcript_error(exc: ValidationError, source: str, model: type[BaseModel]) -> TranscriptError:
    """Render the most informative pydantic error as a didactic TranscriptError.

    One error, not all of them: the hand-rolled validators raised on the first problem
    they found, and a wall of pydantic errors for a single typo is worse than one precise
    message.

    Args:
        exc: The pydantic failure.
        source: Label used as the top-level location prefix (usually the file name).
        model: The model that was validated, for field-name suggestions.
    """
    error = _most_informative(exc.errors())
    loc = _strip_union_tag(tuple(error["loc"]))
    return fail(_location(loc, source, error["type"]), _message(error, loc, model))


def _most_informative(errors: Sequence[ErrorDetails]) -> ErrorDetails:
    """Prefer an unknown-field error over the 'missing' error it causes.

    A transcript with ``rubrik:`` reports both an extra key and a missing ``rubric``.
    Naming the typo is what tells the author what to change.
    """
    return next((e for e in errors if e["type"] == "extra_forbidden"), errors[0])


def _strip_union_tag(loc: Loc) -> Loc:
    """Drop pydantic's trailing union-member tag, which is not a field name."""
    if len(loc) >= 2 and isinstance(loc[-1], str) and loc[-1] in _UNION_TAGS:
        return loc[:-1]
    return loc


def _location(loc: Loc, source: str, kind: str) -> str:
    """Render a loc tuple as a transcript path such as ``turns[1].expect.judge``."""
    if _describes_container(kind, loc):
        loc = loc[:-1]
    if not loc:
        return source
    rendered = "".join(f"[{p}]" if isinstance(p, int) else (f".{p}" if i else str(p)) for i, p in enumerate(loc))
    # An indexed turns[...] path is unambiguous on its own; any other path — including a
    # bare "turns" — reads better prefixed with the file it came from.
    return rendered if rendered.startswith("turns[") else f"{source}.{rendered}"


def _describes_container(kind: str, loc: Loc) -> bool:
    """True when the message is about the container rather than the named field."""
    if kind in _CONTAINER_LOCATED:
        return True
    # A bad item in a list-of-strings is reported against the list, since the didactic
    # message is about the list's shape.
    if kind == "string_type" and loc and isinstance(loc[-1], int):
        return True
    # 'tool' is reported against the entry, because the message names the field itself.
    return bool(loc) and loc[-1] == "tool"


def _message(error: ErrorDetails, loc: Loc, model: type[BaseModel]) -> str:
    """Pick the didactic phrasing for one pydantic error."""
    kind = error["type"]
    value = error.get("input")
    field = str(loc[-1]) if loc and isinstance(loc[-1], str) else ""
    parent = str(loc[-2]) if len(loc) > 1 and isinstance(loc[-2], str) else ""

    if kind == "extra_forbidden":
        return _unknown_field(field, _fields_at(model, loc))
    # These two come before value_error so our own bool/string rejection still reads as a
    # range problem, which is what the author actually needs to fix.
    if field == "threshold":
        return f"must be a number between 0 and 1, got {value!r}"
    if field == "runs":
        return f"must be an integer >= 1, got {value!r}"
    if field == "turns" and kind in {"too_short", "missing"}:
        return "must define at least one turn under 'turns' (an empty transcript would test nothing)"
    if field == "tool":
        return "requires a 'tool' field naming the tool whose arguments to check"
    if kind == "value_error":
        return error["msg"].removeprefix("Value error, ")
    if kind == "missing":
        return f"missing required field {field!r}{_MISSING_HINTS.get(field, '')}"
    if kind == "list_type":
        contents = _LIST_CONTENTS.get(field)
        if contents:
            return f"must be {contents}, got {_type_name(value)}"
        return _LIST_OF_STR.format(type=_type_name(value), value=value, field=field)
    if kind == "string_type" and isinstance(loc[-1], int):
        return _LIST_OF_STR.format(type=_type_name(value), value=value, field=parent)
    if kind in {"model_type", "model_attributes_type", "dict_type"}:
        contents = _MAPPING_CONTENTS.get(field) or _MAPPING_CONTENTS.get(parent)
        if not loc:
            return f"must be a YAML mapping with 'id' and 'turns' keys, got {_type_name(value)}"
        if field == "args":
            return f"must be {contents}, got {_type_name(value)}"
        return f"must be {contents or 'a mapping'}, got {_type_name(value)} ({value!r})"
    if kind in {"bool_parsing", "bool_type"}:
        return f"must be true or false, got {value!r}"
    if kind == "literal_error" and field == "mode":
        return f"must be 'subset' or 'exact', got {value!r}"
    if kind == "string_type":
        if field == "model":
            return f"must be a string like 'openai:gpt-4o', got {_type_name(value)}"
        if field == "audio":
            return f"must be a WAV path string, got {_type_name(value)}"
        return f"must be a string, got {_type_name(value)}"
    if kind == "is_instance_of":
        return f"must be an evaluator with an async 'evaluate(ctx)' method, got {_type_name(value)}"
    return f"is invalid ({kind.replace('_', ' ')}), got {value!r}"


def _unknown_field(field: str, valid: Sequence[str]) -> str:
    """Name the unknown field and suggest the closest valid one.

    stdlib difflib, not a fuzzy-matching dependency: this runs once per validation
    failure over at most ten field names, and it would otherwise be a new runtime
    dependency on every install of the plugin.
    """
    close = difflib.get_close_matches(field, sorted(valid), n=1)
    hint = f" Did you mean {close[0]!r}?" if close else ""
    return f"unknown field {field!r}.{hint} Valid fields: {sorted(valid)}."


def _fields_at(model: type[BaseModel], loc: Loc) -> list[str]:
    """Walk the model tree to the container that rejected the field."""
    current = model
    for item in loc[:-1]:
        if isinstance(item, int):
            continue
        field = current.model_fields.get(str(item))
        nested = None if field is None else _model_of(field.annotation)
        if nested is None:
            break
        current = nested
    return [name for name, f in current.model_fields.items() if not f.exclude]


def _model_of(annotation: object) -> type[BaseModel] | None:
    """Find the BaseModel inside an annotation, looking through unions and lists."""
    from pydantic import BaseModel

    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation
    for arg in getattr(annotation, "__args__", ()):
        found = _model_of(arg)
        if found is not None:
            return found
    return None


def _type_name(value: object) -> str:
    """The YAML-facing name of a value's type."""
    return type(value).__name__
