#!/bin/bash
# UI layer: display recommendation progress and final results.
#
#   header BRAIN                       title + which brain the agents use (codex / offline)
#   progress TICK SECONDS NAME=STATE…  one live status line, redrawn in place (\r)
#   progress-end                       finish the live line
#   agent NAME COUNT SECONDS BRAIN     one summary row per finished agent
#   total SECONDS SEQUENTIAL_SECONDS   parallel time vs. one-after-another time
#   shortlist                          stdin: final list -> numbered cards
#   pick                               stdin: final list -> Gum choice -> chosen title on stdout
#   message TEXT | error TEXT | pause | working LABEL CMD…
# The workflow decides everything; this file only draws.

source "$(dirname "$0")/theme.sh"
FRAMES=(⠋ ⠙ ⠹ ⠸ ⠼ ⠴ ⠦ ⠧ ⠇ ⠏)   # spinner frames for the live progress line

header() {
  clear
  echo
  title "  ✨ Recommendations"
  hint  "  Three agents think in parallel: history · interests · discovery"
  hint  "  Brain: $1"
  echo
}

progress() {   # progress 7 3 history=running interests=done:2s discovery=running
  local tick="$1" secs="$2" line="" pair name state
  shift 2
  for pair in "$@"; do
    name="${pair%%=*}"; state="${pair#*=}"
    case "$state" in
      running) line="$line  \033[38;5;${WARN}m● $name…\033[0m" ;;
      *)       line="$line  \033[38;5;${OK}m✔ $name ${state#done:}\033[0m" ;;
    esac
  done
  # \r jumps back to the start of the line, \033[K clears it: the line redraws in place
  printf "\r\033[K  \033[38;5;${ACCENT}m%s\033[0m %3ss %b" "${FRAMES[$(( tick % 10 ))]}" "$secs" "$line"
}

progress_end() { printf "\r\033[K"; }

agent() {      # agent history 6 2 "offline catalog"
  printf "  \033[38;5;${OK}m✔\033[0m %-10s %2s ideas  in %ss  \033[38;5;${MUTED}m(%s)\033[0m\n" "$1" "$2" "$3" "$4"
}

total() {      # total 3 6   -> wall-clock time vs. the sum of the agents' times
  hint "  total ${1}s in parallel · one after another would take ~${2}s"
}

shortlist() {
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

pick() {
  { cut -d'|' -f1 | sed 's/ *$//'; echo "↩  nothing for now"; } |
    gum choose --cursor.foreground "$ACCENT" --header "Save one to your want-to-read list?" |
    grep -v '^↩'
}

message() { echo; success "$*"; }
error()   { echo; warn "$*"; }

cmd="$1"; shift
case "$cmd" in
  header|progress|progress-end|agent|total|shortlist|pick|message|error|pause|working) "${cmd//-/_}" "$@" ;;
  *) echo "recommendations_screen: unknown command '$cmd'" >&2; exit 1 ;;
esac
