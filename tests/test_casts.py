"""Every asciinema cast fixture must keep printing what its page and runsheet claim.

A cast under ``docs/casts/`` is a recording of a real run. When the plugin's terminal output
changes, the recording silently becomes a lie, and nothing else in the suite notices, because
no cast is executed anywhere else. These tests pin the exact lines the ``docs/why/`` pages
quote, so drift is a red test naming the cast that needs re-recording rather than a stale
video nobody re-watches.

The assertions are deliberately over-specific about whitespace. ``  Run 1 ✅`` at two spaces
with its reasoning at four is not incidental: two of the blocks these replaced invented an
indentation the plugin never produced, and the only thing that would have caught it is a test
that cares.

``pytest.Pytester.copy_example`` cannot be used here: ``pytester_example_dir`` is pinned to
``examples/`` and cannot name a second root.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest

CASTS_DIR = Path(__file__).parent.parent / "docs" / "casts"

# Products of a previous take, never inputs to the next one. .cast-counter especially:
# copying a warm counter in would make 02-flaky-assert fail on the wrong iterations, which is
# the exact bug rec.sh's reset exists to prevent.
_TRANSIENT = shutil.ignore_patterns("__pycache__", ".pytest_cache", ".cast-counter", "*.pyc")


@pytest.fixture(autouse=True)
def _no_live_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Neutralise EVAL_LIVE, exactly as rec.sh does before a take.

    Left set, it turns eval tests on and suppresses the skip hint, which would make
    ``test_collect_only_cast`` fail for a reason that has nothing to do with the cast.
    """
    monkeypatch.delenv("EVAL_LIVE", raising=False)


def _run(pytester: pytest.Pytester, slug: str, *args: str) -> pytest.RunResult:
    """Copy a cast fixture dir into the pytester tmpdir and run pytest in it."""
    shutil.copytree(CASTS_DIR / slug, pytester.path, dirs_exist_ok=True, ignore=_TRANSIENT)
    return pytester.runpytest(*args)


# --------------------------------------------------------------------------------------
# Structural invariants of the docs/casts tree itself
# --------------------------------------------------------------------------------------


def test_no_markdown_anywhere_under_docs_casts() -> None:
    """A .md here would silently become a published, searchable docs page.

    Any .md under docs/ is built into the site even when absent from ``nav`` — verified
    against zensical 0.0.51, which has no ``exclude`` option. That is the whole reason the
    runsheets are .txt, and it is worth a test because the mistake is invisible until
    somebody finds a runsheet in the site search.

    Scoped to what git can carry: ``.pytest_cache/README.md`` is a real thing pytest writes
    here, but it is gitignored, so it can only ever leak into somebody's *local* build. The
    committed tree is what ships, and the docs-build check is what catches the local case.
    """
    committed = [p for p in CASTS_DIR.rglob("*.md") if not {".pytest_cache", "__pycache__"} & set(p.parts)]
    assert committed == []


def test_every_cast_in_casts_txt_has_a_runsheet() -> None:
    """casts.txt is what rec.sh and upload.sh both read, so a missing dir is a broken slug."""
    rows = [
        line.split("|")[0].strip()
        for line in (CASTS_DIR / "casts.txt").read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]
    assert len(rows) == 10
    missing = [slug for slug in rows if not (CASTS_DIR / slug / "runsheet.txt").is_file()]
    assert missing == []


def test_every_cast_directory_is_listed_in_casts_txt() -> None:
    """The other direction: an unlisted dir is a cast rec.sh cannot start."""
    listed = {
        line.split("|")[0].strip()
        for line in (CASTS_DIR / "casts.txt").read_text().splitlines()
        if line.strip() and not line.startswith("#")
    }
    on_disk = {p.name for p in CASTS_DIR.iterdir() if p.is_dir()}
    assert on_disk == listed


@pytest.mark.parametrize("slug", ["07-agent-authors-eval", "10-install"])
def test_scratch_casts_hold_only_a_runsheet(slug: str) -> None:
    """rec.sh decides where to record from this, rather than from a second list.

    A directory holding nothing but its runsheet records in a throwaway dir. Add any file to
    one of these two and rec.sh silently starts recording in the committed directory instead.
    """
    assert [p.name for p in (CASTS_DIR / slug).iterdir()] == ["runsheet.txt"]


@pytest.mark.parametrize(
    "slug",
    [
        "01-pytest-basics",
        "02-flaky-assert",
        "03-runs-and-threshold",
        "04-tool-calls-fail",
        "05-judge-reasoning",
        "06-group-summary",
        "08-collect-only",
        "09-voice-eval",
    ],
)
def test_fixture_casts_pin_their_own_rootdir(slug: str) -> None:
    """Without ``[tool.pytest.ini_options]`` here, pytest walks up to the repo's pyproject.

    It would then inherit ``testpaths = ["tests"]`` and ``filterwarnings = ["error"]``, collect
    nothing in the cast dir, and have no ``yaml_dirs`` to find transcripts under. This is the
    same job the ``examples/*/pyproject.toml`` files already do.
    """
    assert "[tool.pytest.ini_options]" in (CASTS_DIR / slug / "pyproject.toml").read_text()


def test_no_runsheet_puts_the_cache_flag_on_camera() -> None:
    """rec.sh exports ``-p no:cacheprovider`` via PYTEST_ADDOPTS so it never appears.

    Putting it back on a typed line costs 20 columns and pushed 01-pytest-basics' command
    past the 80-column window, which is where it wrapped.

    A runsheet's typed lines are indented exactly two spaces under ``TYPE:``; prose that
    merely *mentions* the flag is indented differently, so match the command shape rather
    than "any line containing the flag".
    """
    offenders = [
        f"{sheet.parent.name}:{n}"
        for sheet in CASTS_DIR.glob("*/runsheet.txt")
        for n, line in enumerate(sheet.read_text().splitlines(), 1)
        if "no:cacheprovider" in line and re.match(r"^ {2}(pytest |for \w+ in |python -m )", line)
    ]
    assert offenders == []


# --------------------------------------------------------------------------------------
# 01-pytest-basics — docs/why/what-is-a-test.md
# --------------------------------------------------------------------------------------


def test_pytest_basics_cast_passes_the_first_node_id(pytester: pytest.Pytester) -> None:
    result = _run(pytester, "01-pytest-basics", "-q", "tests/test_pricing.py::test_discount_applies_to_subtotal")
    result.assert_outcomes(passed=1)


def test_pytest_basics_cast_names_the_test_it_actually_ran(pytester: pytest.Pytester) -> None:
    """The defect this cast exists to fix.

    The old hand-authored block ran ``::test_discount_dont_apply_to_subtotal`` but printed a
    traceback header naming ``test_discount_applies_to_subtotal`` and a body with
    ``code="SPRING"`` — the other test entirely. A real run cannot disagree with itself, and
    this pins that.
    """
    result = _run(pytester, "01-pytest-basics", "-q", "tests/test_pricing.py::test_discount_dont_apply_to_subtotal")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(
        [
            "*_ test_discount_dont_apply_to_subtotal _*",
            '*assert discount(subtotal=100, code="SPRINGS") == 90*',
            "*AssertionError: assert 100 == 90*",
            "*where 100 = discount(subtotal=100, code='SPRINGS')*",
        ]
    )
    assert "test_discount_applies_to_subtotal" not in result.stdout.str()


# --------------------------------------------------------------------------------------
# 02-flaky-assert — docs/why/why-it-breaks.md
# --------------------------------------------------------------------------------------


def test_flaky_assert_cast_fails_on_the_second_and_fifth_process(pytester: pytest.Pytester) -> None:
    """The page's whole claim is the shape ``. F . . F`` over five separate processes.

    The stub keeps its counter in a file precisely so that five processes see five different
    replies; an in-process counter would reset and all five would come out identical.
    """
    shape = ""
    for _ in range(5):
        result = _run(pytester, "02-flaky-assert", "-q", "tests/test_naive.py")
        shape += "F" if result.ret else "."
    assert shape == ".F..F"


def test_flaky_assert_cast_fails_on_the_replies_the_page_quotes(pytester: pytest.Pytester) -> None:
    """Both failing replies are quoted verbatim in the prose, so both must really appear."""
    seen = [_run(pytester, "02-flaky-assert", "-q", "tests/test_naive.py").stdout.str() for _ in range(5)]
    assert "assert 'confirmed' in \"You're all set for tomorrow at 10am, ref BK-4417.\"" in seen[1]
    assert "assert 'confirmed' in 'Done! Your 10am slot is reserved.'" in seen[4]


# --------------------------------------------------------------------------------------
# 03-runs-and-threshold — docs/why/runs-and-tiers.md
# --------------------------------------------------------------------------------------


def test_runs_and_threshold_cast_hides_its_detail_without_rp(pytester: pytest.Pytester) -> None:
    """Pytest prints no report section for a passing test, and the page now says so.

    This is the finding that corrected two pages: both quoted an ``LLM Eval`` block under a
    ``PASSED`` test from a bare ``-vv``, which cannot happen. Pinned in both directions so
    neither the plugin nor the docs can drift back.
    """
    result = _run(pytester, "03-runs-and-threshold", "--agent-eval-live", "-vv")
    result.assert_outcomes(passed=1)
    assert "LLM Eval" not in result.stdout.str()
    # The banner form, not a bare `1 passed in ...`. The hand-written exemplar got this
    # wrong on the -vv half while getting it right on the -rP half.
    result.stdout.fnmatch_lines(["=* 1 passed in *s =*"])


def test_runs_and_threshold_cast_shows_its_detail_with_rp(pytester: pytest.Pytester) -> None:
    result = _run(pytester, "03-runs-and-threshold", "--agent-eval-live", "-vv", "-rP")
    result.assert_outcomes(passed=1)
    detail = result.stdout.str()
    assert "LLM Eval" in detail
    assert "[2/3 runs, score=0.67 >= 0.66]" in detail
    # The exact indentation the page quotes: Run at 2, reasoning at 4, and no ` · ` join.
    assert "  Run 1 ✅\n    All substring and pattern checks passed" in detail
    assert "  Run 2 ❌\n    Reply did not contain any of ['confirmed', 'booked']" in detail
    assert "  Run 3 ✅\n    All substring and pattern checks passed" in detail
    assert " · " not in detail


# --------------------------------------------------------------------------------------
# 04-tool-calls-fail — docs/why/tool-calls.md
# --------------------------------------------------------------------------------------


def test_tool_calls_cast_fails_every_run_on_the_forbidden_tool(pytester: pytest.Pytester) -> None:
    """Deterministic across all three runs, and flat — no turn labels, no per-check tree.

    The old block invented a nested tree under a ``turn 2:`` label. ``_detail_section``
    flattens every turn's every evaluator into one list, so each run really prints turn 1's
    pass and turn 2's failure with nothing saying which is which. The page now explains that
    instead of hiding it, and the counts below are what make the explanation true.
    """
    result = _run(pytester, "04-tool-calls-fail", "--agent-eval-live", "-vv", "tests/test_reschedule.py")
    result.assert_outcomes(failed=1)
    detail = result.stdout.str()
    assert "[0/3 runs, score=0.00 < 0.80]" in detail
    assert (
        detail.count("  Run 1 ❌\n    All tool call checks passed\n    Forbidden tool 'create_booking' was called") == 1
    )
    assert detail.count("    Forbidden tool 'create_booking' was called") == 3
    assert "turn 2:" not in detail
    # At -vv pytest does NOT truncate the short-summary line, and the duration carries a
    # rule banner. The page quoted a -q-shaped summary under a -vv command until an audit
    # caught it, so both halves are pinned.
    result.stdout.fnmatch_lines(
        [
            "FAILED tests/test_reschedule.py::test_reschedule_flow - AssertionError: "
            "LLM eval failed: score=0.00 < threshold=0.80 (0/3 runs passed)",
            "=* 1 failed in *s =*",
        ],
        consecutive=True,
    )


def test_tool_calls_page_quotes_the_traceback_locator_it_would_really_get(pytester: pytest.Pytester) -> None:
    """The page's transcript names a line inside models.py, and that line moves.

    It already did: a docstring-only change to ``models.py`` shifted
    ``assert_threshold``'s ``raise`` by one, silently making the published transcript
    wrong. Rather than hard-code the number here — which would go red on every unrelated
    edit to that file — this asserts the page and a real run agree. It fires exactly when
    the docs go stale and never otherwise, which is the drift this whole file exists for.
    """
    page = (Path(__file__).parent.parent / "docs" / "why" / "tool-calls.md").read_text()
    claimed = re.search(r"models\.py:(\d+): AssertionError", page)
    assert claimed, "tool-calls.md no longer quotes a models.py traceback locator"

    result = _run(pytester, "04-tool-calls-fail", "--agent-eval-live", "-vv", "tests/test_reschedule.py")
    actual = re.search(r"models\.py:(\d+): AssertionError", result.stdout.str())
    assert actual, "the run no longer emits a models.py traceback locator"
    assert claimed.group(1) == actual.group(1), (
        f"docs/why/tool-calls.md quotes models.py:{claimed.group(1)} but the real run reports "
        f"models.py:{actual.group(1)} — update the transcript and re-record 04-tool-calls-fail"
    )


# --------------------------------------------------------------------------------------
# 05-judge-reasoning — docs/why/judges.md
# --------------------------------------------------------------------------------------


def test_judge_reasoning_cast_is_configured_for_a_live_judge() -> None:
    """This cast is recorded live on purpose: the page's point is what a real judge says.

    So the test cannot run it. What it can pin is that the model comes from config rather
    than from an argument invisible on camera — the test file constructs ``JudgeEvaluator``
    with no ``model=``, exactly as the page shows.
    """
    cast = CASTS_DIR / "05-judge-reasoning"
    assert 'model = "openai:gpt-4o-mini"' in (cast / "pyproject.toml").read_text()
    source = (cast / "tests" / "test_reschedule.py").read_text()
    assert "JudgeEvaluator(rubric=RESCHEDULE_RUBRIC)" in source


def test_judge_reasoning_cast_runs_with_the_judge_stubbed(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Everything except the judge call is offline, so everything except it is pinned.

    Stubbed the way ``tests/test_examples.py`` does it — monkeypatching the evaluator's own
    ``evaluate``, never an internal module — so the tool-call half of the turn and the
    threshold arithmetic are still exercised for real.
    """
    from pytest_agent_eval.evaluators.judge import JudgeEvaluator
    from pytest_agent_eval.models import EvalResult

    verdicts = iter([True, False, True])

    async def fake_evaluate(self, ctx):
        passed = next(verdicts)
        return EvalResult(passed=passed, reasoning="stubbed judge (no API key in CI)")

    monkeypatch.setattr(JudgeEvaluator, "evaluate", fake_evaluate)
    result = _run(pytester, "05-judge-reasoning", "--agent-eval-live", "-vv", "-rP", "tests/test_reschedule.py")
    result.assert_outcomes(passed=1)
    detail = result.stdout.str()
    assert "[2/3 runs, score=0.67 >= 0.66]" in detail
    # The judge's reasoning comes first, then the turn's tool-call reasoning. The page's old
    # block omitted the second line entirely.
    assert "  Run 1 ✅\n    stubbed judge (no API key in CI)\n    All tool call checks passed" in detail


# --------------------------------------------------------------------------------------
# 06-group-summary — docs/why/gates.md
# --------------------------------------------------------------------------------------


def test_group_summary_cast_absorbs_one_failure_and_exits_zero(pytester: pytest.Pytester) -> None:
    """Ten booking evals so ``9/10`` is literally true, and group names are never padded.

    The old block padded ``smoke:   4/4`` and claimed a 9/10 that needed ten transcripts that
    did not exist. Both are pinned here: the fixture really has ten ``gate:booking`` plus four
    ``smoke``, and the lines below are matched whole, so a reintroduced pad fails the test.
    """
    result = _run(pytester, "06-group-summary", "--agent-eval-live", "-q")
    result.assert_outcomes(passed=13, failed=1)
    assert result.ret == 0, "the group gate should have overridden the exit code to 0"
    result.stdout.fnmatch_lines(
        [
            "booking: 9/10 passed (90%) >= 90% required -- PASSED",
            "  failures: booking_edge_case",
            "  must_pass: booking_confirmation ok",
            "smoke: 4/4 passed (100%) >= 100% required -- PASSED",
            "exit code overridden to 0: all group thresholds met",
        ],
        consecutive=True,
    )


def test_group_summary_cast_really_has_ten_booking_transcripts() -> None:
    """The page's SVG has "nine green and one red" in its aria-label, so the count is load-bearing."""
    evals = list((CASTS_DIR / "06-group-summary" / "evals").glob("*.yaml"))
    texts = [p.read_text() for p in evals]
    assert sum("gate:booking" in t for t in texts) == 10
    assert sum("[smoke]" in t or "tags: [smoke]" in t for t in texts) == 4


# --------------------------------------------------------------------------------------
# 08-collect-only — docs/why/agents-author-evals.md
# --------------------------------------------------------------------------------------


def test_collect_only_cast_lists_the_transcript_then_hints(pytester: pytest.Pytester) -> None:
    """Node id, blank line, skip hint, count — in that order, which is structural.

    A plugin's ``pytest_terminal_summary`` runs after pytest writes the blank line and before
    it writes the count, so nothing can print below the count. ``consecutive=True`` pins the
    order the page shows.
    """
    result = _run(pytester, "08-collect-only", "--collect-only", "-q")
    result.stdout.fnmatch_lines(
        [
            "tests/evals/reschedule.yaml::reschedule_flow",
            "",
            "1 eval test(s) skipped: live mode is off. Pass --agent-eval-live or set EVAL_LIVE=1.",
            "1 test collected in *",
        ],
        consecutive=True,
    )


# --------------------------------------------------------------------------------------
# 09-voice-eval — docs/why/whats-in-the-box.md
# --------------------------------------------------------------------------------------


def test_voice_cast_collects_and_skips_without_credentials(pytester: pytest.Pytester) -> None:
    """The free half of a Tier B cast, and the ``cost safety`` bullet's own demonstration.

    Collecting a voice transcript must need neither the livekit extra's credentials nor a key;
    the adapter is only constructed when the test runs.
    """
    result = _run(pytester, "09-voice-eval", "--collect-only", "-q")
    result.stdout.fnmatch_lines(
        [
            "tests/evals/booking_voice.yaml::booking_voice",
            "",
            "1 eval test(s) skipped: live mode is off. Pass --agent-eval-live or set EVAL_LIVE=1.",
            "1 test collected in *",
        ],
        consecutive=True,
    )


def test_voice_cast_declares_the_two_wavs_the_page_names() -> None:
    """The page's block shows turn-01.wav and turn-02.wav, so the transcript must ask for both."""
    transcript = (CASTS_DIR / "09-voice-eval" / "tests" / "evals" / "booking_voice.yaml").read_text()
    assert "turn-01.wav" in transcript
    assert "turn-02.wav" in transcript
