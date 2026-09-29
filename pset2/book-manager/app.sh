#!/bin/bash
# Application entry point.
# Checks the tools it needs, then loops: main menu → the workflow for the chosen action.
# No data, recommendation or drawing logic lives here.

cd "$(dirname "$0")" || exit 1

if ! command -v gum >/dev/null 2>&1; then
  echo "Book Manager needs Gum for its interface:  brew install gum" >&2
  exit 1
fi

while true; do
  action=$(./ui/main_menu.sh "$(./workflows/manage_library.sh summary)")
  case "$action" in
    browse|add|search|update|goal) ./workflows/manage_library.sh "$action" ;;
    recommend)                     ./workflows/get_recommendations.sh ;;
    *)                             clear; echo "Happy reading! 📖"; exit 0 ;;
  esac
done
