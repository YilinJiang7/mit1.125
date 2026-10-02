#!/bin/bash
# Recommendation helper (added file): ask Codex for book ideas on behalf of an agent.
#
#   in:   a prompt ($1)
#   out:  only well-formed "Title | Author | Genre | Reason" lines on stdout
#   exit: 1 if Codex is switched off (BOOK_AI=offline), not installed, too slow, or
#         returned nothing usable. The agents treat exit 1 as "use the offline catalog".
#
# Why a separate file: all three agents need the same Codex call + timeout + output check,
# and keeping it here keeps each agent focused on *how it thinks*, not on plumbing.

[ "${BOOK_AI:-auto}" = offline ] && exit 1
command -v codex >/dev/null 2>&1 || exit 1

work=$(mktemp -d)
trap 'kill "$codex_pid" "$watchdog_pid" 2>/dev/null; rm -rf "$work"' EXIT
trap 'exit 1' INT TERM                  # so the EXIT cleanup also runs when we are stopped

# Run Codex in the background so a watchdog can stop it if it takes too long.
( cd "$work" && exec codex exec --skip-git-repo-check --sandbox read-only \
      --output-last-message "$work/answer.txt" "$1

Plain text only: no Markdown, no links, no bold." ) >/dev/null 2>&1 &
codex_pid=$!
( sleep "${BOOK_CODEX_TIMEOUT:-120}"; kill "$codex_pid" 2>/dev/null ) >/dev/null 2>&1 &
watchdog_pid=$!
wait "$codex_pid"; status=$?
kill "$watchdog_pid" 2>/dev/null

[ "$status" -eq 0 ] && [ -s "$work/answer.txt" ] || exit 1

# Clean up Markdown first ("[Title](url)" -> "Title", drop ** and `), then keep lines with
# exactly 4 fields, drop a header row, and strip "1." / "-" list markers.
sed -E 's/\[([^]]*)\]\([^)]*\)/\1/g; s/\*\*//g; s/`//g' "$work/answer.txt" |
  awk -F'|' 'NF == 4 && tolower($1) !~ /^[ \t]*title[ \t]*$/ {
               sub(/^[ \t]*([0-9]+[.)]|[-*])[ \t]*/, ""); print }' | grep .
