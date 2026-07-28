"""Normalisation of framework-specific tool-call arguments."""

from __future__ import annotations

import json

from pytest_agent_eval.models import JsonMapping


def coerce_args(raw: object) -> JsonMapping | None:
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
