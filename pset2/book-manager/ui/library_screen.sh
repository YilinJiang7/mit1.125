#!/bin/bash
# UI layer: the library screens.
#
#   library_screen.sh browse | add | search | update | goal
#
# Each screen asks with Gum, hands the answer to workflows/manage_library.sh, and draws
# what comes back (table, book card, goal bar). No data access and no decisions here:
# the workflow decides, this file only asks and shows.

HERE="$(cd "$(dirname "$0")" && pwd)"
WORKFLOW="$HERE/../workflows/manage_library.sh"
source "$HERE/theme.sh"

# ---------- drawing (read pipe records on stdin) ----------

table() {
  awk -F' [|] ' -v bold="$(tput bold 2>/dev/null)" -v dim="$(tput dim 2>/dev/null)" -v off="$(tput sgr0 2>/dev/null)" '
    function cut(s, w) { return length(s) > w ? substr(s, 1, w - 1) "…" : s }
    function stars(r,   s, i) { if (r == "") return "·"; for (i = 1; i <= 5; i++) s = s (i <= r ? "★" : "☆"); return s }
    BEGIN {
      icon["owned"] = "📦"; icon["want-to-read"] = "🔖"; icon["reading"] = "📖"; icon["finished"] = "✅"
      printf "%s  %-3s %-34s %-20s %-26s %-15s %s%s\n", bold, "#", "Title", "Author", "Genre", "Status", "Rating", off
    }
    { printf "  %-3s %-34s %s%-20s%s %-26s %s %-12s %s\n", NR, cut($1, 34), dim, cut($2, 20), off, cut($3, 26), icon[$5], $5, stars($6) }
    END { printf "%s  %d book%s%s\n", dim, NR, (NR == 1 ? "" : "s"), off }'
}

card() {
  local t a g y s r f k l
  IFS='|' read -r t a g y s r f k l
  trim() { echo "$1" | sed 's/^ *//; s/ *$//'; }
  t=$(trim "$t"); a=$(trim "$a"); g=$(trim "$g"); y=$(trim "$y"); s=$(trim "$s")
  r=$(trim "$r"); f=$(trim "$f"); k=$(trim "$k"); l=$(trim "$l")
  gum style --border rounded --border-foreground "$ACCENT" --padding "1 3" --margin "1 2" --width 80 \
    "$(title "$t")" \
    "$(hint "by ${a:-unknown author}${y:+ · $y}")" "" \
    "Genre     $g" \
    "Status    $s${f:+  (finished $f)}" \
    "Rating    $(stars "$r")" "" \
    "$(gum style --foreground "$SOFT" "Takeaway")" \
    "${k:-— none yet: add one with \"Update a book\" —}" "" \
    "$(hint "$l")"
}

goal_bar() {   # goal_bar 2026 4 12   (stdin: the books finished this year)
  local year="$1" done="$2" target="$3" width=30 filled bar="" i pace
  [ "$target" -gt 0 ] 2>/dev/null || target=1
  filled=$(( done * width / target )); [ "$filled" -gt "$width" ] && filled=$width
  for i in $(seq 1 $width); do [ "$i" -le "$filled" ] && bar="$bar█" || bar="$bar░"; done
  pace=$(( target * 10#$(date +%j) / 365 ))
  echo
  title "  🎯 $year reading goal"
  echo "  $(gum style --foreground "$ACCENT" "$bar")  $done / $target books"
  if   [ "$done" -ge "$target" ]; then success "Goal reached, $(( done - target )) extra"
  elif [ "$done" -ge "$pace" ];   then success "On track (pace for today: $pace)"
  else warn "$(( pace - done )) behind pace (pace for today: $pace)"; fi
  echo
  gum style --foreground "$SOFT" "  What I took away this year"
  awk -F' [|] ' '{ printf "  • %s (%s)\n      %s\n", $1, $7, ($8 == "" ? "— no takeaway yet —" : $8) }'
}

show_book() { clear; "$WORKFLOW" details "$1" | card; }

# ---------- asking (answer on stdout; empty = cancelled) ----------

pick() {       # stdin: records → the chosen title
  cut -d'|' -f1 | sed 's/ *$//' |
    gum filter --height 12 --indicator.foreground "$ACCENT" --header "$1" --placeholder "type to filter · Esc Esc to go back"
}
ask_status()   { gum choose --header "Reading status" owned want-to-read reading finished; }
ask_rating()   { gum choose --header "Your rating" "5 ★★★★★" "4 ★★★★☆" "3 ★★★☆☆" "2 ★★☆☆☆" "1 ★☆☆☆☆" | cut -c1; }
ask_takeaway() { gum input --width 90 --char-limit 200 --header "One-sentence takeaway: what will you remember?" --value "$1"; }
confirm() {    # confirm "Question?" [no]
  local default=true; [ "$2" = no ] && default=false
  gum confirm --selected.background "$ACCENT" --default="$default" "$1"
}

ask_finished_details() {   # a book was just marked finished: rating + takeaway
  local rating takeaway
  rating=$(ask_rating) && [ -n "$rating" ] && "$WORKFLOW" update "$1" rating "$rating"
  takeaway=$(ask_takeaway) && [ -n "$takeaway" ] && "$WORKFLOW" update "$1" takeaway "$takeaway"
}

# ---------- screens ----------

browse() {
  local books title
  books=$("$WORKFLOW" list)
  [ -n "$books" ] || { warn "Your library is empty. Add a book first."; pause; return; }
  clear; echo
  echo "$books" | table; echo
  title=$(echo "$books" | pick "Open a book for details")
  [ -n "$title" ] && show_book "$title" && pause
}

add() {
  local title author status record rc
  clear
  title=$(gum input --header "Title" --placeholder "e.g. The Book of Why")
  [ -n "$title" ] || return
  author=$(gum input --header "Author (optional, helps the metadata lookup)" --placeholder "e.g. Judea Pearl")
  status=$(ask_status) || return
  record=$(working "Looking up metadata…" "$WORKFLOW" prepare "$title | $author" "$status"); rc=$?
  if [ "$rc" -eq 2 ]; then warn "That book is already in your library."; pause; return; fi
  echo "$record" | card                                                        # preview
  confirm "Save this book?" || return
  "$WORKFLOW" save "$record" || { pause; return; }
  title=$(echo "$record" | cut -d'|' -f1 | sed 's/ *$//')
  [ "$status" = finished ] && ask_finished_details "$title"
  echo; success "Saved \"$title\" as $status."
  pause
}

search() {
  local term results title
  clear
  term=$(gum input --header "Search your library" --width 70 \
           --placeholder "any word · or status:reading · genre:mystery · author:christie · rating:4")
  [ -n "$term" ] || return
  if ! results=$("$WORKFLOW" search "$term"); then
    echo; warn "No books match \"$term\"."; pause; return
  fi
  clear; echo; echo "  Results for \"$term\""; echo
  echo "$results" | table; echo
  title=$(echo "$results" | pick "Open a result for details")
  [ -n "$title" ] && show_book "$title" && pause
}

update() {
  local title what value
  clear
  title=$("$WORKFLOW" list | pick "Which book?")
  [ -n "$title" ] || return
  show_book "$title"
  what=$(gum choose --header "What do you want to change?" status rating takeaway) || return
  case "$what" in
    status)   value=$(ask_status) && [ -n "$value" ] && "$WORKFLOW" update "$title" status "$value" &&
                [ "$value" = finished ] && ask_finished_details "$title" ;;
    rating)   value=$(ask_rating) && [ -n "$value" ] && "$WORKFLOW" update "$title" rating "$value" ;;
    takeaway) value=$(ask_takeaway "$("$WORKFLOW" details "$title" | cut -d'|' -f8 | sed 's/^ *//; s/ *$//')") &&
                "$WORKFLOW" update "$title" takeaway "$value" ;;
  esac
  show_book "$title"
  success "Updated."
  pause
}

goal() {
  local year count target new
  read -r year count target <<< "$("$WORKFLOW" goal-status)"
  clear
  "$WORKFLOW" finished-this-year | goal_bar "$year" "$count" "$target"
  echo
  if confirm "Change your $year goal?" no; then
    new=$(gum input --header "Books to finish this year" --value "$target")
    [ -n "$new" ] && "$WORKFLOW" set-goal "$new" && { echo; success "Goal set to $new books."; }
    pause
  fi
}

case "$1" in
  browse|add|search|update|goal) "$1" ;;
  *) echo "usage: library_screen.sh browse|add|search|update|goal" >&2; exit 1 ;;
esac
