#!/bin/bash
# Workflow layer: coordinate library operations.
# Connects UI actions to book components and the data layer; does no drawing and no storage itself.
#
#   manage_library.sh browse    Data → UI table → pick → details
#   manage_library.sh add       User input → metadata → preview → database
#   manage_library.sh search    Search request → search component → results → UI
#   manage_library.sh update    pick a book → change status / rating / takeaway → database
#   manage_library.sh goal      finished-this-year → goal progress + takeaways
#   manage_library.sh summary   one status line for the main menu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DB="$ROOT/data/book_database.sh"
UI="$ROOT/ui/library_screen.sh"
YEAR=$(date +%Y)

field() { echo "$1" | awk -F' [|] ' -v i="$2" '{ print $i }'; }   # field "$record" 3 -> genre

show_book() { "$DB" get "$1" | "$UI" details; }

browse() {
  local books title
  books=$("$DB" list)
  [ -n "$books" ] || { "$UI" error "Your library is empty. Add a book first."; "$UI" pause; return; }
  clear; echo
  echo "$books" | "$UI" table
  echo
  title=$(echo "$books" | "$UI" pick "Open a book for details") || return
  [ -n "$title" ] && clear && show_book "$title" && "$UI" pause
}

finish_details() {   # a book just became "finished": date it, then ask for rating + takeaway
  local title="$1" rating takeaway
  [ -n "$(field "$("$DB" get "$title")" 7)" ] || "$DB" update "$title" finished "$(date +%F)"
  rating=$("$UI" ask-rating) && [ -n "$rating" ] && "$DB" update-rating "$title" "$rating"
  takeaway=$("$UI" ask-takeaway) && [ -n "$takeaway" ] && "$DB" update "$title" takeaway "$takeaway"
}

add() {
  local input meta status record
  clear
  input=$("$UI" ask-book) || return                                        # 1. user input
  meta=$("$UI" working "Looking up metadata…" "$ROOT/books/fetch_book_metadata.sh" "$input")  # 2. metadata
  "$DB" exists "$(field "$meta" 1)" && { "$UI" error "\"$(field "$meta" 1)\" is already in your library."; "$UI" pause; return; }
  status=$("$UI" ask-status) || return
  record=$(echo "$meta" | awk -F' [|] ' -v s="$status" '{ print $1 " | " $2 " | " $3 " | " $4 " | " s " |  |  |  | " $5 }')
  echo "$record" | "$UI" details                                             # 3. preview
  "$UI" confirm "Save this book?" || return
  echo "$record" | "$DB" add || { "$UI" pause; return; }                     # 4. database
  [ "$status" = finished ] && finish_details "$(field "$record" 1)"
  "$UI" message "Saved \"$(field "$record" 1)\" as $status."
  "$UI" pause
}

search() {
  local term results title
  clear
  term=$("$UI" ask-search) || return
  [ -n "$term" ] || return
  if ! results=$(echo "$term" | "$ROOT/books/search_books.sh"); then        # search request → component
    "$UI" error "No books match \"$term\"."; "$UI" pause; return
  fi
  clear; echo; echo "  Results for \"$term\""; echo
  echo "$results" | "$UI" table                                             # results → UI
  echo
  title=$(echo "$results" | "$UI" pick "Open a result for details") || return
  [ -n "$title" ] && clear && show_book "$title" && "$UI" pause
}

update() {
  local title what value
  clear
  title=$("$DB" list | "$UI" pick "Which book?") || return
  [ -n "$title" ] || return
  clear; show_book "$title"
  what=$("$UI" ask-field) || return
  case "$what" in
    status)   value=$("$UI" ask-status) || return
              "$DB" update-status "$title" "$value"
              [ "$value" = finished ] && finish_details "$title" ;;
    rating)   value=$("$UI" ask-rating) && [ -n "$value" ] && "$DB" update-rating "$title" "$value" ;;
    takeaway) value=$("$UI" ask-takeaway "$(field "$("$DB" get "$title")" 8)") &&
                "$DB" update "$title" takeaway "$value" ;;
  esac
  clear; show_book "$title"
  "$UI" message "Updated."
  "$UI" pause
}

finished_this_year() {
  "$DB" list | awk -F' [|] ' -v y="$YEAR" '$5 == "finished" && substr($7, 1, 4) == y'
}

goal() {
  local target books count new
  target=$("$DB" goal)
  books=$(finished_this_year)
  count=$(echo "$books" | grep -c .)
  clear
  echo "$books" | grep . | "$UI" goal "$YEAR" "$count" "$target"
  echo
  if "$UI" confirm "Change your $YEAR goal?" no; then
    new=$("$UI" ask-goal "$target") && [ -n "$new" ] && "$DB" set-goal "$new" && "$UI" message "Goal set to $new books."
    "$UI" pause
  fi
}

summary() {
  "$DB" list | awk -F' [|] ' -v y="$YEAR" -v goal="$("$DB" goal)" '
    { total++; count[$5]++; if ($5 == "finished" && substr($7, 1, 4) == y) done++ }
    END { printf "%s goal %d/%d  ·  %d reading  ·  %d want to read  ·  %d books\n",
                 y, done, goal, count["reading"], count["want-to-read"], total }'
}

case "$1" in
  browse|add|search|update|goal|summary) "$1" ;;
  *) echo "usage: manage_library.sh browse|add|search|update|goal|summary" >&2; exit 1 ;;
esac
