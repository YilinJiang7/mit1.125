#!/bin/bash
# UI layer: main application menu.
#   in:  $1 = a status line to show under the title (the workflow layer builds it)
#   out: the chosen action on stdout: browse | add | search | update | recommend | goal | quit
# Interaction only: this file never touches data and never decides what happens next.

source "$(dirname "$0")/theme.sh"

clear >&2   # stdout is reserved for the answer
gum style --border double --border-foreground "$ACCENT" --padding "1 4" --margin "1 2" --align center \
  "$(title "📚  Yilin's Book Manager")" "" "$(hint "${1:-}")" >&2

choice=$(gum choose --cursor.foreground "$ACCENT" --header "  What would you like to do?" --height 10 \
  "📚  Browse library" \
  "➕  Add a book" \
  "🔍  Search library" \
  "📝  Update a book" \
  "✨  Get recommendations" \
  "🎯  Reading goal & takeaways" \
  "👋  Quit")

case "$choice" in
  *Browse*)          echo browse ;;
  *Add*)             echo add ;;
  *Search*)          echo search ;;
  *Update*)          echo update ;;
  *recommendations*) echo recommend ;;
  *goal*)            echo goal ;;
  *)                 echo quit ;;     # Quit, Esc or Ctrl+C
esac
