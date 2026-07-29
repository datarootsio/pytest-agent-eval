"""Normalisation of framework-specific tool-call arguments."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pytest_agent_eval.models import ToolArgs


def coerce_args(raw: Mapping[str, object] | str | None) -> ToolArgs | None:
    """Coerce a framework's tool-call arguments into a dict, or None when uncapturable.

    The parameter names the three shapes the four call sites actually pass: LangChain's
    ``ToolCall["args"]`` mapping, OpenAI's JSON string, and the ``getattr`` default of
    ``None`` where an SDK object carries no arguments at all. ``Mapping``, not ``dict``,
    because a framework is free to hand back its own mapping type and turning that into
    "not captured" would be a lie about arguments we plainly have.

    The dict is rebuilt key by key rather than handed straight through, which is what makes
    the return annotation true rather than asserted: the comprehension *constructs* a
    ``dict[str, object]`` from whatever the mapping holds. ``str(k)`` rather than rejecting
    a non-string key, for the same reason.

    Args:
        raw: Whatever the framework exposes as call arguments — a mapping, a JSON
            string (OpenAI-style), or None.

    Returns:
        The arguments as a dict, or None when they cannot be represented as one.
        None means "arguments not captured", which argument evaluators report
        distinctly from an argument mismatch.
    """
    if isinstance(raw, str):
        # json.loads returns whatever the document held, so the Mapping check below is
        # what turns `[1, 2]` or `null` into "not captured" rather than a crash.
        try:
            parsed: object = json.loads(raw)
        except ValueError:
            return None
    else:
        parsed = raw
    # isinstance, not a bare `raw is None` check: the guard is also for callers without a
    # type checker, and a stray scalar out of an untyped SDK must still say "not captured".
    if not isinstance(parsed, Mapping):
        return None
    return {str(k): v for k, v in parsed.items()}
