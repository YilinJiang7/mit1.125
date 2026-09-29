#!/bin/bash
# UI layer: display library information and ask library questions.
#
# Display (read pipe records on stdin, draw them):
#   table                  numbered list of books
#   details                one book as a card
#   goal YEAR DONE GOAL    reading-goal progress bar + takeaways from this year's books
# Ask (draw a Gum prompt, print the answer on stdout; empty answer = cancelled):
#   pick HEADER            choose one book from the records on stdin -> title
#   ask-book | ask-search | ask-field | ask-status | ask-rating | ask-takeaway [OLD] | ask-goal OLD
#   confirm QUESTION [no]  exit 0 for yes ("no" makes No the default button)
# Plus: message TEXT | error TEXT | pause | working LABEL CMD… (spinner while CMD runs)
# No data access and no decisions here: the workflow decides what to show and when.

source "$(dirname "$0")/theme.sh"

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

details() {
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

goal() {   # goal 2026 4 12   (stdin: the books finished this year)
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

pick() {
  cut -d'|' -f1 | sed 's/ *$//' |
    gum filter --height 12 --indicator.foreground "$ACCENT" --header "$1" --placeholder "type to filter · Esc Esc to go back"
}

ask_book() {
  local t a
  t=$(gum input --header "Title" --placeholder "e.g. The Book of Why") || return 1
  [ -n "$t" ] || return 1
  a=$(gum input --header "Author (optional, helps the metadata lookup)" --placeholder "e.g. Judea Pearl")
  echo "$t | $a"
}

ask_search() {
  gum input --header "Search your library" --width 70 \
    --placeholder "any word · or status:reading · genre:mystery · author:christie · rating:4"
}

ask_field()    { gum choose --header "What do you want to change?" "status" "rating" "takeaway"; }
ask_status()   { gum choose --header "Reading status" owned want-to-read reading finished; }
ask_rating()   { gum choose --header "Your rating" "5 ★★★★★" "4 ★★★★☆" "3 ★★★☆☆" "2 ★★☆☆☆" "1 ★☆☆☆☆" | cut -c1; }
ask_takeaway() { gum input --width 90 --char-limit 200 --header "One-sentence takeaway: what will you remember?" --value "$1"; }
ask_goal()     { gum input --header "Books to finish this year" --value "$1"; }
confirm() {    # confirm "Question?" [no]
  local default=true; [ "$2" = no ] && default=false
  gum confirm --selected.background "$ACCENT" --default="$default" "$1"
}
message()      { echo; success "$*"; }
error()        { echo; warn "$*"; }

cmd="$1"; shift
case "$cmd" in
  table|details|goal|pick|ask-book|ask-search|ask-field|ask-status|ask-rating|ask-takeaway|ask-goal|confirm|message|error|pause|working)
    "${cmd//-/_}" "$@" ;;   # ask-book -> ask_book
  *) echo "library_screen: unknown command '$cmd'" >&2; exit 1 ;;
esac
