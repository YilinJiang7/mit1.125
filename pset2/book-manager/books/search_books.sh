#!/bin/bash
# Book component: search the user's library.
#
#   ./books/search_books.sh "history"          free text: title, author, genre, status, takeaway
#   echo "history" | ./books/search_books.sh   same, through a pipe
#   ./books/search_books.sh "status:reading"   field filter  (title: author: genre: status: year:)
#   ./books/search_books.sh "rating:4"         books rated 4 or higher
#
# Output: matching pipe records on stdout (same shape as `book_database.sh list`).
# Exit 1 when nothing matches, so callers can say "no results".

DB="$(cd "$(dirname "$0")/.." && pwd)/data/book_database.sh"

term="$1"; [ -n "$term" ] || IFS= read -r term
[ -n "$term" ] || { echo "usage: search_books.sh TERM" >&2; exit 1; }

case "$term" in
  *:*) field=$(echo "${term%%:*}" | tr '[:upper:]' '[:lower:]'); value="${term#*:}"
       results=$("$DB" list | awk -F'|' -v field="$field" -v value="$value" '
         function trim(s) { gsub(/^[ \t]+|[ \t]+$/, "", s); return s }
         BEGIN { split("title author genre year status rating", names, " ")
                 for (i in names) col[names[i]] = i }
         !(field in col) { exit }
         { v = trim($(col[field])) }
         field == "rating" { if (v != "" && v + 0 >= value + 0) print; next }
         index(tolower(v), tolower(trim(value))) { print }') ;;
  *)   results=$("$DB" search "$term") ;;
esac

[ -n "$results" ] || exit 1
echo "$results"
