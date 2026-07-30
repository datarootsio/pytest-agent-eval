#!/usr/bin/env bash
#
# Upload one recorded cast and print the line to paste into docs/why/.
#
# Usage:   docs/casts/upload.sh <slug>
#
# Run `asciinema auth` FIRST, once, ever. asciinema.org deletes any recording that is
# not linked to an account after 7 days, and an uploaded-then-expired cast is worse
# than a missing one: the page renders a dead player instead of the placeholder that
# tells you how to fix it.
#
# Uploaded unlisted, not public: these are documentation figures reached from the page
# they illustrate, and they have no business in asciinema.org's browse listings.

set -euo pipefail

CASTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ ${1-} == "--help" || ${1-} == "-h" || $# -ne 1 ]]; then
  # See rec.sh's usage(): the header comment is the help text, printed up to the first
  # non-comment line, so editing the header cannot leak code into --help.
  awk 'NR>2 && !/^#/ {exit} NR>2 {sub(/^# ?/, ""); print}' "${BASH_SOURCE[0]}"
  [[ $# -eq 1 ]] && exit 0
  exit 2
fi

slug="$1"
cast="$CASTS_DIR/$slug.cast"
if [[ ! -f $cast ]]; then
  printf 'upload.sh: no recording at %s — run rec.sh %s first\n' "$cast" "$slug" >&2
  exit 1
fi

row="$(grep -E "^${slug}[[:space:]]*\|" "$CASTS_DIR/casts.txt" || true)"
page="$(printf '%s' "$row" | awk -F'|' '{print $3}' | sed 's/^ *//; s/ *$//')"

output="$(asciinema upload --visibility unlisted "$cast" 2>&1 | tee /dev/stderr)"

# The id is the last path segment of the returned URL. Matched rather than assumed to
# be on a known line: asciinema prints a variable amount of surrounding chatter.
url="$(printf '%s' "$output" | grep -oE 'https://[^[:space:]]*/a/[A-Za-z0-9]+' | tail -1 || true)"
if [[ -z $url ]]; then
  printf '\nupload.sh: no recording URL in the output above. Nothing to paste.\n' >&2
  exit 1
fi

printf '\n--- paste into %s ---\n' "${page:-docs/why/}"
printf '       data-cast-id="%s"\n' "${url##*/}"
printf -- '---\n'
