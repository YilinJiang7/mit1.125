#!/bin/bash
# Workflow layer: coordinate recommendation agents.
#
#                     ┌→ recommend_from_history.sh ───┐
#   library+interests ├→ recommend_from_interests.sh ─┼→ cat → refine_recommendations.sh → UI
#                     └→ recommend_for_discovery.sh ──┘
#
#   1. start the three agents in parallel          (&  and  $!)
#   2. stream progress while they run              (poll each PID, redraw one status line)
#   3. wait for all of them                        (wait = the synchronization point)
#   4. combine their outputs                       (cat)
#   5. pipe the combined list into refinement      (|)
#   6. send the shortlist to the UI, and save the book the user picks

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REC="$ROOT/recommendations"
UI="$ROOT/ui/recommendations_screen.sh"
DB="$ROOT/data/book_database.sh"

AGENTS=(history interests discovery)
SCRIPTS=(recommend_from_history.sh recommend_from_interests.sh recommend_for_discovery.sh)

work=$(mktemp -d)                       # each agent writes its own files here: no shared output
stop_tree() {                           # stop a process and everything it started
  local child                           # (agent → ask_codex.sh → codex), children first
  for child in $(pgrep -P "$1" 2>/dev/null); do stop_tree "$child"; done
  kill "$1" 2>/dev/null
}
cleanup() { local pid; for pid in "${PIDS[@]}"; do stop_tree "$pid"; done; rm -rf "$work"; }
trap cleanup EXIT
trap 'exit 130' INT TERM                # Ctrl+C: stop the agents too, not just this script

if [ "${BOOK_AI:-auto}" != offline ] && command -v codex >/dev/null 2>&1; then
  "$UI" header "Codex (falls back to the offline catalog if it fails)"
else
  "$UI" header "offline catalog (install the Codex CLI for AI picks)"
fi

# 1. Parallel: '&' puts each agent in the background, '$!' is the PID it just got.
start=$(date +%s)
for i in 0 1 2; do
  "$REC/${SCRIPTS[$i]}" > "$work/${AGENTS[$i]}.txt" 2> "$work/${AGENTS[$i]}.log" &
  PIDS[$i]=$!
done

# 2. Streaming progress: 'kill -0 PID' only asks "are you still alive?", it sends nothing.
tick=0
while :; do
  now=$(date +%s); running=0; states=()
  for i in 0 1 2; do
    if kill -0 "${PIDS[$i]}" 2>/dev/null; then
      running=$((running + 1)); states[$i]="${AGENTS[$i]}=running"
    else
      [ -n "${TOOK[$i]}" ] || TOOK[$i]=$(( now - start ))
      states[$i]="${AGENTS[$i]}=done:${TOOK[$i]}s"
    fi
  done
  "$UI" progress "$tick" "$(( now - start ))" "${states[@]}"
  [ "$running" -eq 0 ] && break
  tick=$((tick + 1)); sleep 0.2
done
"$UI" progress-end

# 3. Synchronization: wait for every agent and collect its exit status.
for i in 0 1 2; do
  wait "${PIDS[$i]}" || echo "  (${AGENTS[$i]} agent exited with an error; its ideas are skipped)" >&2
  "$UI" agent "${AGENTS[$i]}" "$(grep -c . "$work/${AGENTS[$i]}.txt")" "${TOOK[$i]}" \
               "$(tail -n 1 "$work/${AGENTS[$i]}.log" | sed 's/^[a-z]* agent: //')"
done
"$UI" total "$(( $(date +%s) - start ))" "$(( TOOK[0] + TOOK[1] + TOOK[2] ))"

# 4 + 5 + 6. Combine → refine → display, as one pipeline (tee keeps a copy for the choice below).
cat "$work/history.txt" "$work/interests.txt" "$work/discovery.txt" \
  | "$REC/refine_recommendations.sh" \
  | tee "$work/shortlist.txt" \
  | "$UI" shortlist

if [ ! -s "$work/shortlist.txt" ]; then
  "$UI" error "No new ideas this time: add or rate a few books first."
  "$UI" pause; exit 0
fi

# Save the chosen book: reuse the metadata component for year + link, then the data layer.
choice=$("$UI" pick < "$work/shortlist.txt")
if [ -n "$choice" ]; then
  line=$(awk -F' [|] ' -v t="$choice" '$1 == t' "$work/shortlist.txt" | head -n 1)
  meta=$("$UI" working "Looking up \"$choice\"…" "$ROOT/books/fetch_book_metadata.sh" "$line")
  # keep the agent's genre (it uses the app's vocabulary), take year + link from the metadata
  echo "$line | $meta" | awk -F' [|] ' '{ print $1 " | " $2 " | " $3 " | " $9 " | want-to-read |  |  |  | " $10 }' |
    "$DB" add && "$UI" message "Added \"$choice\" to your want-to-read list."
fi
"$UI" pause
