"""Normalisation of framework-specific tool-call arguments."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pytest_agent_eval.models import ToolArgs


def coerce_args(raw: Mapping[str, object] | str | None) -> ToolArgs | None:
    """Coerce a framework's tool-call arguments into a dict, or None when uncapturable.

    ``Mapping``, not ``dict``: a framework may hand back its own mapping type, and
    reporting "not captured" for arguments we plainly have would be a lie. The dict is
    rebuilt key by key — including ``str(k)`` — so the return annotation is constructed
    rather than asserted.

    Args:
        raw: Whatever the framework exposes as call arguments — a mapping, a JSON
            string (OpenAI-style), or None.

    Returns:
        The arguments as a dict, or None when they cannot be represented as one.
        None means "arguments not captured", which argument evaluators report
        distinctly from an argument mismatch.
    """
    if isinstance(raw, str):
        try:
            parsed: object = json.loads(raw)
        except ValueError:
            return None
    else:
        parsed = raw
    # The guard is also for callers with no type checker, so a stray scalar out of an
    # untyped SDK must say "not captured" rather than raise.
    if not isinstance(parsed, Mapping):
        return None
    return {str(k): v for k, v in parsed.items()}
