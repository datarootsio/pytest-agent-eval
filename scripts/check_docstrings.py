"""Fail if griffe emits any warning while parsing the package's docstrings.

This is the regression guard for the API reference, and it exists because nothing
else actually guards it:

* ``zensical build --strict`` does not. Verified against zensical 0.0.51: the flag
  is forwarded to the Rust runtime, whose issue collector reports "No issues
  found" and exits 0 even while griffe warnings are printed to the same output.
  ``zensical serve --strict`` is blunter still -- it prints "Strict mode is
  currently unsupported."
* A local build does not, because a warm ``./.cache/`` replays the cached
  ``api-reference/*`` render, so the python handler never re-collects and griffe
  never re-parses. The warnings simply stop appearing.

What griffe warns about here is not cosmetic. A Google-style ``Args:`` section in
a *class* docstring is validated against ``Class.parameters``, which is literally
``all_members["__init__"].parameters``. Classes whose ``__init__`` is generated at
runtime -- pydantic models, ``NamedTuple``, a ``str`` subclass with only
``__new__`` -- have no static ``__init__``, so that list is empty: every documented
name warns, and the rendered table loses its type column and marks every field
``required``. Such classes must use ``Attributes:`` instead, which griffe resolves
from the real class-body annotation. ``@dataclass`` docstrings keep ``Args:``:
griffe's built-in dataclasses extension synthesises an ``__init__`` for them, so
they get correct types *and* a defaults column.

Note the asymmetry this guard cannot cover: the ``Attributes:`` parser never
validates names against the class body, so a typo'd attribute name renders a
phantom row silently rather than warning.

Usage::

    python scripts/check_docstrings.py
"""

from __future__ import annotations

import logging
from pathlib import Path

import griffe

REPO_ROOT = Path(__file__).parent.parent
PACKAGE = "pytest_agent_eval"


class _WarningCollector(logging.Handler):
    """Capture every warning-or-worse record griffe logs while parsing."""

    def __init__(self) -> None:
        super().__init__()
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        if record.levelno >= logging.WARNING:
            self.messages.append(record.getMessage())


def _parse_every_docstring(obj: object, seen: set[int]) -> None:
    """Walk the tree, forcing each docstring to parse so warnings are emitted.

    ``Docstring.parsed`` is lazy, so merely loading the package warns about
    nothing; the sections have to be materialised to exercise the parser.
    """
    if id(obj) in seen:
        return
    seen.add(id(obj))
    docstring = getattr(obj, "docstring", None)
    if docstring is not None:
        _ = docstring.parsed
    for member in getattr(obj, "members", {}).values():
        if not member.is_alias:
            _parse_every_docstring(member, seen)


def collect_warnings() -> list[str]:
    """Load the package with griffe and return every docstring warning raised."""
    collector = _WarningCollector()
    root = logging.getLogger()
    root.addHandler(collector)
    previous_level = root.level
    root.setLevel(logging.WARNING)
    try:
        package = griffe.load(
            PACKAGE,
            docstring_parser=griffe.Parser.google,
            extensions=griffe.load_extensions(),
            search_paths=[str(REPO_ROOT / "src")],
            submodules=True,
        )
        _parse_every_docstring(package, set())
    finally:
        root.removeHandler(collector)
        root.setLevel(previous_level)
    return collector.messages


def main() -> int:
    """Report any docstring warnings; return a non-zero exit code if there are any."""
    warnings = collect_warnings()
    if not warnings:
        print(f"griffe: no docstring warnings in {PACKAGE}")
        return 0
    print(f"griffe: {len(warnings)} docstring warning(s) in {PACKAGE}:")
    for message in warnings:
        print(f"  {message}")
    print(
        "\nA class whose __init__ is generated at runtime (pydantic, NamedTuple, "
        "__new__-only) must document its fields under 'Attributes:', not 'Args:'."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
