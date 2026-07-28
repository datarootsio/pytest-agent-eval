"""Group-level pass thresholds: config parsing and result aggregation."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from pytest_agent_eval.models import OutcomeName


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


@dataclass(frozen=True, slots=True)
class EvalOutcome:
    """Outcome of one test item, as consumed by group aggregation.

    Args:
        identity: Stable name for must_pass matching — the transcript id for
            YAML items, the test name (with parametrization) for functions.
        nodeid: Full pytest nodeid.
        outcome: "passed", "failed", or "skipped".
        tags: Transcript tags (from the agent_eval marker), empty for plain tests.
        markers: Names of all pytest markers on the item.
    """

    identity: str
    nodeid: str
    outcome: OutcomeName
    tags: list[str] = field(default_factory=list)
    markers: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class GroupResult:
    """Aggregated result of one group over a session's outcomes.

    Args:
        group: The group config this result was computed for.
        total: Matched outcomes that ran (passed or failed; skipped excluded).
        passed_count: Matched outcomes that passed.
        skipped_count: Matched outcomes that were skipped.
        failing: Identities of matched outcomes that failed.
        failed_nodeids: Nodeids of matched outcomes that failed.
        must_pass_failed: must_pass entries whose matching test(s) failed.
        must_pass_missing: must_pass entries with no ran (non-skipped) match.
    """

    group: GroupConfig
    total: int = 0
    passed_count: int = 0
    skipped_count: int = 0
    failing: list[str] = field(default_factory=list)
    failed_nodeids: list[str] = field(default_factory=list)
    must_pass_failed: list[str] = field(default_factory=list)
    must_pass_missing: list[str] = field(default_factory=list)

    @property
    def matched(self) -> bool:
        """True if any outcome (even a skipped one) matched this group."""
        return self.total > 0 or self.skipped_count > 0

    @property
    def skipped(self) -> bool:
        """True if outcomes matched but every one of them was skipped."""
        return self.total == 0 and self.skipped_count > 0

    @property
    def pass_rate(self) -> float:
        """Fraction of ran, matched outcomes that passed (0.0 when none ran)."""
        return self.passed_count / self.total if self.total else 0.0

    @property
    def passed(self) -> bool:
        """True if the group ran, met its threshold, and no must_pass entry failed."""
        return self.total > 0 and self.pass_rate >= self.group.threshold and not self.must_pass_failed


def _matches_group(group: GroupConfig, outcome: EvalOutcome) -> bool:
    return bool(set(group.tags) & set(outcome.tags)) or bool(set(group.pytest_markers) & set(outcome.markers))


def _matches_identity(entry: str, identity: str) -> bool:
    return identity == entry or identity.startswith(entry + "[")


def _evaluate_group(group: GroupConfig, outcomes: Sequence[EvalOutcome]) -> GroupResult:
    """Aggregate one group's membership and must_pass assertions into a result."""
    members = [o for o in outcomes if _matches_group(group, o)]
    ran = [o for o in members if o.outcome != "skipped"]
    # `failing` is "not passed" while must_pass below is "== failed". Both are
    # deliberate and not interchangeable: an unexpected outcome name counts against
    # the pass rate but must not trip a must_pass gate.
    failed = [o for o in ran if o.outcome != "passed"]

    must_pass_ran = {entry: _ran_for(entry, outcomes) for entry in group.must_pass}
    return GroupResult(
        group=group,
        total=len(ran),
        passed_count=len(ran) - len(failed),
        skipped_count=len(members) - len(ran),
        failing=[o.identity for o in failed],
        failed_nodeids=[o.nodeid for o in failed],
        # Config order, because test output pins the exact line order.
        must_pass_failed=[e for e, r in must_pass_ran.items() if r and any(o.outcome == "failed" for o in r)],
        must_pass_missing=[e for e, r in must_pass_ran.items() if not r],
    )


def _ran_for(entry: str, outcomes: Sequence[EvalOutcome]) -> list[EvalOutcome]:
    """Every non-skipped outcome whose identity the must_pass entry names."""
    return [o for o in outcomes if _matches_identity(entry, o.identity) and o.outcome != "skipped"]


def evaluate_groups(groups: Sequence[GroupConfig], outcomes: Sequence[EvalOutcome]) -> list[GroupResult]:
    """Aggregate session outcomes into per-group results.

    Membership is tag/marker based (OR). must_pass entries are assertions over
    every ran outcome, not selectors: an entry that failed anywhere fails the
    group; an entry that never ran is reported as missing (a warning, not a
    failure, so partial selection doesn't flip gates).

    Args:
        groups: Parsed group configs.
        outcomes: One EvalOutcome per executed (or skipped) test item.

    Returns:
        One GroupResult per group, in config order.
    """
    return [_evaluate_group(group, outcomes) for group in groups]


def format_group_summary_lines(results: list[GroupResult]) -> list[str]:
    """Render group results as terminal summary lines.

    Lines starting with "WARNING:" flag groups that matched nothing (or
    must_pass entries that never ran) — callers may highlight them.

    Args:
        results: Output of evaluate_groups.

    Returns:
        Plain-text lines, one group block after another.
    """
    lines: list[str] = []
    for result in results:
        group = result.group
        if not result.matched:
            lines.append(f"WARNING: group '{group.name}' matched no tests")
        elif result.skipped:
            lines.append(f"{group.name}: SKIPPED ({result.skipped_count} matched, all skipped)")
        else:
            status = "PASSED" if result.passed else "FAILED"
            lines.append(
                f"{group.name}: {result.passed_count}/{result.total} passed "
                f"({result.pass_rate:.0%}) >= {group.threshold:.0%} required -- {status}"
            )
            if result.failing:
                lines.append(f"  failures: {', '.join(result.failing)}")
        # must_pass is an assertion over every ran outcome, independent of membership,
        # so surface it even when the group's selectors matched nothing.
        for entry in group.must_pass:
            if entry in result.must_pass_failed:
                lines.append(f"  must_pass: {entry} FAILED")
            elif entry in result.must_pass_missing:
                lines.append(f"  WARNING: must_pass entry '{entry}' did not run")
            else:
                lines.append(f"  must_pass: {entry} ok")
    return lines


def build_group_markdown_lines(results: list[GroupResult]) -> list[str]:
    """Render group results as a markdown report section.

    Args:
        results: Output of evaluate_groups.

    Returns:
        Markdown lines for a "## Groups" section (heading included).
    """
    lines = ["## Groups", "", "| Group | Passed | Total | Rate | Threshold | Status |", "|---|---|---|---|---|---|"]
    notes: list[str] = []
    for result in results:
        group = result.group
        if not result.matched:
            status_cell = "❌ must_pass FAILED" if result.must_pass_failed else "⚠️ NO MATCH"
            lines.append(f"| {group.name} | - | 0 | - | {group.threshold:.2f} | {status_cell} |")
        elif result.skipped:
            lines.append(f"| {group.name} | - | 0 | - | {group.threshold:.2f} | ⏭ SKIPPED |")
        else:
            status = "✅ PASS" if result.passed else "❌ FAIL"
            lines.append(
                f"| {group.name} | {result.passed_count} | {result.total} "
                f"| {result.pass_rate:.2f} | {group.threshold:.2f} | {status} |"
            )
            if result.failing:
                notes.append(f"- `{group.name}` failures: {', '.join(result.failing)}")
        notes.extend(f"- `{group.name}` must_pass FAILED: {entry}" for entry in result.must_pass_failed)
        notes.extend(f"- `{group.name}` must_pass did not run: {entry}" for entry in result.must_pass_missing)
    if notes:
        lines.append("")
        lines.extend(notes)
    return lines


_KNOWN_KEYS = ("threshold", "tags", "pytest_markers", "must_pass")


def parse_groups(raw: object) -> list[GroupConfig]:
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
