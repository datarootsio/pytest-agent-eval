#!/usr/bin/env bash
#
# LAUNCHER ONLY. This script does not simulate a single keystroke.
#
# It resets the cast's fixture directory, puts you inside it with a clean `$ ` prompt
# and the repo's venv already active, starts the recording, and then gets out of the
# way. You type the lines in that cast's runsheet.txt. Ctrl-D ends the take.
#
# Everything it does before handing over is off camera on purpose: what a reader sees
# is the bare `pytest ...` they would type themselves, not `uv run pytest` from a
# directory named after somebody's laptop.
#
# Usage:   docs/casts/rec.sh <slug>
#          docs/casts/rec.sh --help
#
# See CONTRIBUTING.md, "Recording the docs/why casts", for the whole runbook —
# starting with `asciinema auth`, which is step 0 and not optional.

set -euo pipefail

CASTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$CASTS_DIR/../.." && pwd)"

# One window size for every cast, or the embedded players end up different widths and
# the pages look ragged. 80 columns is what pytest's rule lines are already sized for,
# and it stays legible on a phone.
WINDOW_SIZE="80x24"

# Applied at PLAYBACK time from the cast header, not baked into the capture: it caps
# the pauses while you find the next line in the runsheet without touching the recorded
# timing. Re-tune it later by editing the header — no re-record needed.
IDLE_TIME_LIMIT="1.5"

usage() {
  # The header comment IS the help text, printed up to the first line that is not a
  # comment. A fixed line range would silently start leaking code the next time someone
  # edits the header — it already did, printing `set -euo pipefail` as if it were help.
  awk 'NR>2 && !/^#/ {exit} NR>2 {sub(/^# ?/, ""); print}' "${BASH_SOURCE[0]}"
  printf '\nSlugs:\n'
  grep -E '^[0-9]{2}-' "$CASTS_DIR/casts.txt" | sed 's/^/  /'
}

if [[ ${1-} == "--help" || ${1-} == "-h" || $# -ne 1 ]]; then
  usage
  [[ $# -eq 1 ]] && exit 0
  exit 2
fi

slug="$1"
row="$(grep -E "^${slug}[[:space:]]*\|" "$CASTS_DIR/casts.txt" || true)"
if [[ -z $row ]]; then
  printf 'rec.sh: unknown slug %s\n\n' "$slug" >&2
  usage >&2
  exit 2
fi
title="$(printf '%s' "$row" | awk -F'|' '{print $2}' | sed 's/^ *//; s/ *$//')"

if [[ ! -x "$REPO_ROOT/.venv/bin/pytest" ]]; then
  printf "rec.sh: no pytest in %s/.venv — run 'uv sync --all-extras --group dev' first\n" "$REPO_ROOT" >&2
  exit 1
fi

fixture_dir="$CASTS_DIR/$slug"
runsheet="$fixture_dir/runsheet.txt"
if [[ ! -f $runsheet ]]; then
  printf 'rec.sh: no runsheet at %s\n' "$runsheet" >&2
  exit 1
fi

# A cast whose directory holds nothing but its runsheet records in a throwaway
# directory instead: 10-install *is* `uv add` into an empty project, and
# 07-agent-authors-eval needs an AGENTS.md beside it, which cannot live under docs/
# without becoming a published page. Derived from the directory rather than from a
# second list, so there is nothing to keep in sync.
other_files="$(find "$fixture_dir" -mindepth 1 -not -name runsheet.txt -print -quit)"
if [[ -z $other_files ]]; then
  rec_dir="${TMPDIR:-/tmp}/pytest-agent-eval-casts/$slug"
  rm -rf "$rec_dir"
  mkdir -p "$rec_dir"
  scratch=1
  printf 'scratch dir: %s\n' "$rec_dir"
else
  scratch=0
  rec_dir="$fixture_dir"
  # A retake has to start from the same state as the first take. Without this, the second
  # recording of 02-flaky-assert starts from a warm counter file and fails on the wrong
  # iterations.
  #
  # Deliberately NOT `git clean -fdx` on the fixture directory. A cast dir that is not
  # committed yet is entirely untracked, so `git clean` on it deletes the fixture itself —
  # that is not a hypothetical, it ate 01-pytest-basics once. The reset therefore restores
  # tracked files and removes only artifacts it can name.
  if git -C "$REPO_ROOT" ls-files --error-unmatch "$fixture_dir" >/dev/null 2>&1; then
    git -C "$REPO_ROOT" checkout -- "$fixture_dir"
    # Untracked strays a previous take left behind. No -x: the ignored artifacts are
    # removed by name below, and -x here is what made this destructive.
    git -C "$REPO_ROOT" clean -fdq "$fixture_dir"
  else
    printf 'note: %s is not committed yet — resetting artifacts only, not tracked content\n' "$slug"
  fi
  # Named, not globbed away: .pytest_cache and __pycache__ are gitignored repo-wide so
  # `git clean` without -x cannot see them, and the flaky counter is what actually decides
  # which iterations of 02-flaky-assert fail.
  find "$fixture_dir" -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true
  rm -rf "$fixture_dir/.pytest_cache"
  rm -f "$fixture_dir/.cast-counter" "$fixture_dir/eval.md"
fi

printf 'recording:   %s\n' "$title"
printf 'runsheet:    %s\n' "${runsheet#"$REPO_ROOT"/}"
printf 'output:      %s\n' "${CASTS_DIR#"$REPO_ROOT"/}/$slug.cast"
printf 'window:      %s   idle-time-limit: %ss\n\n' "$WINDOW_SIZE" "$IDLE_TIME_LIMIT"
printf 'Type the runsheet lines. Ctrl-D when done.\n\n'

# Activated here, before the recording starts, so `pytest` on camera is the repo's own
# editable install and the activation itself is never filmed. The cast then shows the
# working tree, which is the version these docs are being built for.
# shellcheck disable=SC1091
source "$REPO_ROOT/.venv/bin/activate"

# The prompt has to match the `$ ` already in every console block in docs/why/, not
# show a hostname and a cwd. VIRTUAL_ENV_PROMPT would otherwise leak a `(...)` prefix.
# PS1 is bash's and PROMPT is zsh's; we force bash below, so PS1 is the one that acts —
# PROMPT is set too in case the recorded shell is ever changed.
unset VIRTUAL_ENV_PROMPT
export PS1='$ '
export PROMPT='$ '

# Keeps .pytest_cache out of a committed fixture dir without putting
# `-p no:cacheprovider` on camera. That flag is 20 characters of noise a reader would never
# type, and it is what pushed 01-pytest-basics' command line past 80 columns and made it
# wrap. pytest does not echo PYTEST_ADDOPTS in its header (checked, 9.1.1), so nothing about
# this is visible in the recording — only the absence of a cache directory afterwards.
export PYTEST_ADDOPTS='-p no:cacheprovider'

# EVAL_LIVE would silently turn eval tests on and make `pytest --collect-only` print no
# skip hint — which is half the lesson of 08-collect-only.
unset EVAL_LIVE

# A scratch cast types `uv` commands, and uv compares VIRTUAL_ENV against the project it
# finds. Since we activated the REPO's venv above, `uv add` in a throwaway project opens
# with `warning: VIRTUAL_ENV=/Users/.../.venv does not match the project environment path
# .venv and will be ignored; use --active ...` — the recorder's absolute path on camera,
# plus advice that would install the PyPI wheel over the repo's editable install. PATH is
# what makes `pytest` resolve, not VIRTUAL_ENV, so dropping it costs nothing.
# Only in the scratch branch: a fixture cast never runs uv, and a half-activated env is
# the more surprising state of the two.
if [[ $scratch -eq 1 ]]; then
  unset VIRTUAL_ENV
fi

cd "$rec_dir"
exec asciinema rec \
  --overwrite \
  --window-size "$WINDOW_SIZE" \
  --idle-time-limit "$IDLE_TIME_LIMIT" \
  --title "$title" \
  -c "bash --norc --noprofile" \
  "$CASTS_DIR/$slug.cast"
