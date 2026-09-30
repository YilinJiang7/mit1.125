#!/bin/bash
# UI layer: main application menu.
# Loops: draw the banner (with a status line the library workflow computes), let the user
# choose with Gum, open the matching screen. Interaction only: no data access, no logic.

HERE="$(cd "$(dirname "$0")" && pwd)"
LIBRARY="$HERE/library_screen.sh"
RECOMMEND="$HERE/recommendations_screen.sh"
WORKFLOW="$HERE/../workflows/manage_library.sh"
source "$HERE/theme.sh"

while true; do
  clear
  gum style --border double --border-foreground "$ACCENT" --padding "1 4" --margin "1 2" --align center \
    "$(title "📚  Yilin's Book Manager")" "" "$(hint "$("$WORKFLOW" summary)")"

  choice=$(gum choose --cursor.foreground "$ACCENT" --header "  What would you like to do?" --height 10 \
    "📚  Browse library" \
    "➕  Add a book" \
    "🔍  Search library" \
    "📝  Update a book" \
    "✨  Get recommendations" \
    "🎯  Reading goal & takeaways" \
    "👋  Quit")

  case "$choice" in
    *Browse*)          "$LIBRARY" browse ;;
    *Add*)             "$LIBRARY" add ;;
    *Search*)          "$LIBRARY" search ;;
    *Update*)          "$LIBRARY" update ;;
    *recommendations*) "$RECOMMEND" show ;;
    *goal*)            "$LIBRARY" goal ;;
    *)                 clear; echo "Happy reading! 📖"; exit 0 ;;   # Quit, Esc or Ctrl+C
  esac
done
