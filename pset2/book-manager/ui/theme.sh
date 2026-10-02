#!/bin/bash
# shellcheck disable=SC2034
# UI layer (added file): shared look & feel, sourced by the three UI screens.
# Colors and a few tiny helpers live here once, instead of being copied into every screen.

ACCENT=212   # pink   - titles, cursor, highlights
SOFT=99      # purple - secondary headings  (these are used by the screens that source this file)
MUTED=244    # grey   - hints and details
OK=42        # green  - done / saved
WARN=214     # orange - running / warnings

title()   { gum style --bold --foreground "$ACCENT" "$*"; }
hint()    { gum style --foreground "$MUTED" "$*"; }
success() { gum style --foreground "$OK" "  ✔ $*"; }
warn()    { gum style --foreground "$WARN" "  ! $*"; }
pause()   { echo; hint "  press any key to go back…"; read -r -s -n 1 < /dev/tty; }

stars() {   # stars 4  ->  ★★★★☆   (empty rating -> "not rated")
  case "$1" in
    [1-5]) local s="" i; for i in 1 2 3 4 5; do [ "$i" -le "$1" ] && s="${s}★" || s="${s}☆"; done; echo "$s" ;;
    *) echo "not rated" ;;
  esac
}

working() { # working "Looking up…" command args...  -> spinner while it runs, then its stdout
  local label="$1" out rc; shift
  out=$(mktemp)
  gum spin --spinner dot --spinner.foreground "$ACCENT" --title " $label" -- \
    sh -c '"$@" > "$0" 2>/dev/null' "$out" "$@"
  rc=$?
  cat "$out"; rm -f "$out"
  return $rc
}
