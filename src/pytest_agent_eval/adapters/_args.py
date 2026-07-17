"""Normalisation of framework-specific tool-call arguments."""

from __future__ import annotations

import json
from typing import Any


def coerce_args(raw: Any) -> dict[str, Any] | None:
    """Coerce a framework's tool-call arguments into a dict, or None when uncapturable.

    Args:
        raw: Whatever the framework exposes as call arguments — a dict, a JSON
            string (OpenAI-style), or anything else.

    Returns:
        The arguments as a dict, or None when they cannot be represented as one.
        None means "arguments not captured", which argument evaluators report
        distinctly from an argument mismatch.
    """
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except ValueError:
            return None
        return parsed if isinstance(parsed, dict) else None
    return None
