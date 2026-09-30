#!/bin/bash
# Application entry point.
# Checks the tools it needs, then hands control to the main menu.
# The call chain is strictly top-down:
#   app.sh → ui/ → workflows/ → books/ + recommendations/ → data/book_database.sh → data files

cd "$(dirname "$0")" || exit 1

if ! command -v gum >/dev/null 2>&1; then
  echo "Book Manager needs Gum for its interface:  brew install gum" >&2
  exit 1
fi

exec ./ui/main_menu.sh
