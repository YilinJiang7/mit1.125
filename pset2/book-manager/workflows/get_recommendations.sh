#!/bin/bash
# Workflow layer: coordinate recommendation agents.
# Called by the UI (or by you, in a pipe); calls only the recommendation components.
#
#                     ┌→ recommend_from_history.sh ───┐
#   library+interests ├→ recommend_from_interests.sh ─┼→ cat → refine_recommendations.sh → stdout
#                     └→ recommend_for_discovery.sh ──┘
#
#   1. start the three agents in parallel          (&  and  $!)
#   2. stream progress while they run              (poll each PID with kill -0, emit a status event)
#   3. wait for all of them                        (wait = the synchronization point)
#   4. combine their outputs                       (cat)
#   5. pipe the combined list into refinement      (|)
#   6. the final shortlist goes to stdout, for whoever called us (normally the UI)
#
#   ./workflows/get_recommendations.sh                  shortlist only: a clean stage for a pipe
#   ./workflows/get_recommendations.sh --progress       also stream progress events on stderr:
#        brain codex|offline
#        tick TICK SECONDS history=running interests=done:2s discovery=running   (every 0.2 s)
#        agent NAME IDEAS SECONDS BRAIN                                          (after wait)
#        total SECONDS SEQUENTIAL_SECONDS
#        warn TEXT

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REC="$ROOT/recommendations"

PROGRESS=0; [ "$1" = "--progress" ] && PROGRESS=1
event() { [ "$PROGRESS" -eq 1 ] && echo "$*" >&2; }

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

if [ "${BOOK_AI:-auto}" != offline ] && command -v codex >/dev/null 2>&1; then event brain codex
else event brain offline; fi

# 1. Parallel: '&' puts each agent in the background, '$!' is the PID it just got.
start=$(date +%s)
for i in 0 1 2; do
  "$REC/${SCRIPTS[$i]}" > "$work/${AGENTS[$i]}.txt" 2> "$work/${AGENTS[$i]}.log" &
  PIDS[$i]=$!
done

# 2. Streaming progress: 'kill -0 PID' only asks "are you still alive?", it sends nothing.
tick=0
while [ "$PROGRESS" -eq 1 ]; do
  now=$(date +%s); running=0; states=""
  for i in 0 1 2; do
    if kill -0 "${PIDS[$i]}" 2>/dev/null; then
      running=$((running + 1)); states="$states ${AGENTS[$i]}=running"
    else
      [ -n "${TOOK[$i]}" ] || TOOK[$i]=$(( now - start ))
      states="$states ${AGENTS[$i]}=done:${TOOK[$i]}s"
    fi
  done
  event tick "$tick" "$(( now - start ))" $states
  [ "$running" -eq 0 ] && break
  tick=$((tick + 1)); sleep 0.2
done

# 3. Synchronization: wait for every agent and collect its exit status.
for i in 0 1 2; do
  wait "${PIDS[$i]}" || event warn "${AGENTS[$i]} agent exited with an error; its ideas are skipped"
  [ -n "${TOOK[$i]}" ] || TOOK[$i]=$(( $(date +%s) - start ))
  event agent "${AGENTS[$i]}" "$(grep -c . "$work/${AGENTS[$i]}.txt")" "${TOOK[$i]}" \
              "$(tail -n 1 "$work/${AGENTS[$i]}.log" | sed 's/^[a-z]* agent: //')"
done
event total "$(( $(date +%s) - start ))" "$(( TOOK[0] + TOOK[1] + TOOK[2] ))"

# 4 + 5 + 6. Combine → refine → stdout.
cat "$work/history.txt" "$work/interests.txt" "$work/discovery.txt" | "$REC/refine_recommendations.sh"
