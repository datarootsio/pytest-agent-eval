"""Normalisation of framework-specific tool-call arguments."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pytest_agent_eval.models import ToolArgs


def coerce_args(raw: object) -> ToolArgs | None:
    """Coerce a framework's tool-call arguments into a dict, or None when uncapturable.

    The dict is rebuilt key by key rather than handed straight through, which is what makes
    the return annotation true rather than asserted: ``raw`` is an untyped mapping out of
    someone else's SDK, and the comprehension *constructs* a ``dict[str, object]`` from
    whatever it holds. ``str(k)`` rather than rejecting a non-string key, because dropping
    a call's arguments over an exotic key would report "not captured" for arguments we
    plainly have.

    Args:
        raw: Whatever the framework exposes as call arguments — a dict, a JSON
            string (OpenAI-style), or anything else.

    Returns:
        The arguments as a dict, or None when they cannot be represented as one.
        None means "arguments not captured", which argument evaluators report
        distinctly from an argument mismatch.
    """
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return None
    if not isinstance(raw, dict):
        return None
    return {str(k): v for k, v in raw.items()}
