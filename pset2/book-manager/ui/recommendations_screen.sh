#!/bin/bash
# UI layer: the recommendations screen.
#
#   recommendations_screen.sh show
#
# Runs workflows/get_recommendations.sh --progress and splits its two streams:
#   stderr → progress events, read line by line and drawn live (one status line, redrawn in place)
#   stdout → the final shortlist, drawn as cards once the workflow is done
# Then lets the user save one pick through the library workflow. Draws and asks; decides nothing.

HERE="$(cd "$(dirname "$0")" && pwd)"
RECOMMEND="$HERE/../workflows/get_recommendations.sh"
LIBRARY="$HERE/../workflows/manage_library.sh"
source "$HERE/theme.sh"
FRAMES=(⠋ ⠙ ⠹ ⠸ ⠼ ⠴ ⠦ ⠧ ⠇ ⠏)   # spinner frames for the live progress line

draw_progress() {   # stdin: event lines from the workflow
  local kind a b c d
  while read -r kind a b c d; do
    case "$kind" in
      brain) [ "$a" = codex ] && hint "  Brain: Codex (falls back to the offline catalog if it fails)" \
                              || hint "  Brain: offline catalog (install the Codex CLI for AI picks)"
             echo ;;
      tick)  local line="" pair name state
             for pair in $c $d; do
               name="${pair%%=*}"; state="${pair#*=}"
               case "$state" in
                 running) line="$line  \033[38;5;${WARN}m● ${name}…\033[0m" ;;
                 *)       line="$line  \033[38;5;${OK}m✔ $name ${state#done:}\033[0m" ;;
               esac
             done
             # \r jumps back to the start of the line, \033[K clears it: the line redraws in place
             printf "\r\033[K  \033[38;5;${ACCENT}m%s\033[0m %3ss %b" "${FRAMES[$(( a % 10 ))]}" "$b" "$line" ;;
      agent) printf "\r\033[K  \033[38;5;${OK}m✔\033[0m %-10s %2s ideas  in %ss  \033[38;5;${MUTED}m(%s)\033[0m\n" \
               "$a" "$b" "$c" "$d" ;;
      total) hint "  total ${a}s in parallel · one after another would take ~${b}s" ;;
      warn)  warn "$a $b $c $d" ;;
    esac
  done
}

draw_shortlist() {  # stdin: Title | Author | Genre | Reason | sources
  echo
  gum style --foreground "$SOFT" --bold "  Your shortlist"
  awk -F' [|] ' -v a="\033[38;5;${ACCENT}m" -v m="\033[38;5;${MUTED}m" -v off="\033[0m" '
    { n = split($5, s, "+")
      agree = (n > 1 ? "  ★ " n " agents agree" : "")
      printf "\n  %s%d. %s%s — %s\n", a, NR, $1, off, $2
      printf "     %s%s · from %s%s%s\n", m, $3, $5, agree, off
      printf "     ↳ %s\n", $4 }'
  echo
}

show() {
  local shortlist choice line
  shortlist=$(mktemp); trap 'rm -f "$shortlist"' EXIT
  clear; echo
  title "  ✨ Recommendations"
  hint  "  Three agents think in parallel: history · interests · discovery"

  # 2>&1 sends the workflow's stderr (events) into the pipe; >file keeps stdout (shortlist) apart
  "$RECOMMEND" --progress 2>&1 >"$shortlist" | draw_progress

  if [ ! -s "$shortlist" ]; then
    warn "No new ideas this time: add or rate a few books first."; pause; return
  fi
  draw_shortlist < "$shortlist"

  choice=$({ cut -d'|' -f1 "$shortlist" | sed 's/ *$//'; echo "↩  nothing for now"; } |
             gum choose --cursor.foreground "$ACCENT" --header "Save one to your want-to-read list?")
  case "$choice" in ""|↩*) return ;; esac
  line=$(awk -F' [|] ' -v t="$choice" '$1 == t' "$shortlist" | head -n 1)
  working "Saving \"$choice\"…" "$LIBRARY" save-recommendation "$line" &&
    success "Added \"$choice\" to your want-to-read list."
  pause
}

case "$1" in
  show) show ;;
  *) echo "usage: recommendations_screen.sh show" >&2; exit 1 ;;
esac
