#!/bin/bash
# Workflow layer: coordinate library operations.
# Called by the UI; calls the book components and the data layer. Never draws, never asks:
# every command takes plain arguments / stdin and answers with pipe records on stdout.
#
#   list                              every book
#   search TERM   (or TERM on stdin)  Search Request → search component → matching books   (exit 1 = none)
#   details TITLE                     one book
#   prepare "Title | Author" STATUS   User Input → metadata component → a full record, not saved yet
#                                     (exit 2 = already in the library)
#   save [RECORD]  (or on stdin)      record → database; a "finished" book is dated today
#   save-recommendation LINE          shortlist line → metadata (year, link) → want-to-read → database
#   update TITLE FIELD VALUE          status | rating | takeaway → database; "finished" dates the book
#   goal-status                       "YEAR DONE TARGET", e.g. "2026 4 12"
#   finished-this-year                the books behind DONE, with their takeaways
#   set-goal N
#   summary                           one status line for the main menu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DB="$ROOT/data/book_database.sh"
BOOKS="$ROOT/books"
YEAR=$(date +%Y)
TODAY=$(date +%F)

field() { echo "$1" | awk -F' [|] ' -v i="$2" '{ print $i }'; }   # field "$record" 3 -> genre

list()    { "$DB" list; }
details() { "$DB" get "$1"; }

search() {
  local term="$1"; [ -n "$term" ] || IFS= read -r term
  echo "$term" | "$BOOKS/search_books.sh"                                      # pipe into the component
}

prepare() {                          # "Title | Author" + status -> full 9-field record
  local meta
  meta=$("$BOOKS/fetch_book_metadata.sh" "$1" 2>/dev/null)                     # metadata component
  "$DB" exists "$(field "$meta" 1)" && { echo "\"$(field "$meta" 1)\" is already in your library" >&2; exit 2; }
  echo "$meta" | awk -F' [|] ' -v s="${2:-want-to-read}" '{ print $1 " | " $2 " | " $3 " | " $4 " | " s " |  |  |  | " $5 }'
}

# shellcheck disable=SC2120
save() {                             # a finished book without a date gets today's date, then → database
  local record="$1"; [ -n "$record" ] || IFS= read -r record
  echo "$record" | awk -F'|' -v today="$TODAY" '
    { for (i = 1; i <= 9; i++) { f[i] = $i; gsub(/^[ \t]+|[ \t]+$/, "", f[i]) }
      if (f[5] == "finished" && f[7] == "") f[7] = today
      out = f[1]; for (i = 2; i <= 9; i++) out = out " | " f[i]; print out }' | "$DB" add
}

save_recommendation() {              # keep the agent's genre (app vocabulary), take year + link from metadata
  local line="$1" meta
  meta=$("$BOOKS/fetch_book_metadata.sh" "$line" 2>/dev/null)
  echo "$line | $meta" | awk -F' [|] ' '{ print $1 " | " $2 " | " $3 " | " $9 " | want-to-read |  |  |  | " $10 }' | save
}

update() {
  local title="$1" what="$2" value="$3"
  case "$what" in
    status)   "$DB" update-status "$title" "$value" || exit 1
              if [ "$value" = finished ] && [ -z "$(field "$("$DB" get "$title")" 7)" ]; then
                "$DB" update "$title" finished "$TODAY"
              fi ;;
    rating)   "$DB" update-rating "$title" "$value" ;;
    takeaway) "$DB" update "$title" takeaway "$value" ;;
    *)        echo "manage_library: can only update status, rating or takeaway" >&2; exit 1 ;;
  esac
}

finished_this_year() { "$DB" list | awk -F' [|] ' -v y="$YEAR" '$5 == "finished" && substr($7, 1, 4) == y'; }

goal_status() { echo "$YEAR $(finished_this_year | grep -c .) $("$DB" goal)"; }

summary() {
  "$DB" list | awk -F' [|] ' -v y="$YEAR" -v goal="$("$DB" goal)" '
    { total++; count[$5]++; if ($5 == "finished" && substr($7, 1, 4) == y) done++ }
    END { printf "%s goal %d/%d  ·  %d reading  ·  %d want to read  ·  %d books\n",
                 y, done, goal, count["reading"], count["want-to-read"], total }'
}

cmd="$1"; [ $# -gt 0 ] && shift
case "$cmd" in
  list|details|search|prepare|save|update|summary)  "$cmd" "$@" ;;
  save-recommendation|goal-status|finished-this-year) "${cmd//-/_}" "$@" ;;
  set-goal) "$DB" set-goal "$1" ;;
  *) sed -n '2,19p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 1 ;;
esac
