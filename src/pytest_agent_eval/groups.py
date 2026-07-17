"""Group-level pass thresholds: config parsing and result aggregation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class GroupConfig:
    """Configuration for one quality-gate group under [tool.agent_eval.groups].

    Args:
        name: Group name (the table key).
        threshold: Fraction of matched, non-skipped tests that must pass (0.0-1.0).
        tags: Transcript tags selecting members (OR-combined with pytest_markers).
        pytest_markers: Pytest marker names selecting members.
        must_pass: Test identities that must individually pass whenever they run.
    """

    name: str
    threshold: float = 1.0
    tags: list[str] = field(default_factory=list)
    pytest_markers: list[str] = field(default_factory=list)
    must_pass: list[str] = field(default_factory=list)


_KNOWN_KEYS = ("threshold", "tags", "pytest_markers", "must_pass")


def parse_groups(raw: Any) -> list[GroupConfig]:
    """Parse the raw [tool.agent_eval.groups] mapping into GroupConfig objects.

    Unlike the rest of [tool.agent_eval] (where unknown keys are silently
    ignored), group config is validated strictly: a typo'd key or threshold
    here would silently disable a CI gate.

    Args:
        raw: The raw mapping from pyproject.toml.

    Returns:
        One GroupConfig per group table.

    Raises:
        ValueError: On non-table groups, unknown keys, non-numeric or
            out-of-range thresholds, or non-string-list selector fields.
    """
    if not isinstance(raw, dict):
        raise ValueError(f"[tool.agent_eval.groups] must be a table of group tables, got {type(raw).__name__}")

    groups: list[GroupConfig] = []
    for name, cfg in raw.items():
        prefix = f"[tool.agent_eval.groups.{name}]"
        if not isinstance(cfg, dict):
            raise ValueError(f"{prefix} must be a table, got {type(cfg).__name__}")

        unknown = sorted(set(cfg) - set(_KNOWN_KEYS))
        if unknown:
            raise ValueError(f"{prefix}: unknown key(s) {unknown}; valid keys are {list(_KNOWN_KEYS)}")

        threshold = cfg.get("threshold", 1.0)
        if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not 0.0 <= threshold <= 1.0:
            raise ValueError(f"{prefix}.threshold must be a number between 0 and 1, got {threshold!r}")

        lists: dict[str, list[str]] = {}
        for key in ("tags", "pytest_markers", "must_pass"):
            value = cfg.get(key, [])
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                raise ValueError(f"{prefix}.{key} must be a list of strings, got {value!r}")
            lists[key] = value

        groups.append(
            GroupConfig(
                name=name,
                threshold=float(threshold),
                tags=lists["tags"],
                pytest_markers=lists["pytest_markers"],
                must_pass=lists["must_pass"],
            )
        )
    return groups
