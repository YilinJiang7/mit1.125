#!/usr/bin/env bash
set -euo pipefail
# Re-run selection only against saved eligible evidence and current snapshots.
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
if [ "$#" -ne 1 ] || [ ! -f "$1/run.json" ]; then echo 'usage: compare_policy.sh RUN_DIR' >&2; exit 2; fi
export RUN_DIR="$1"
started=$(date -u +%Y-%m-%dT%H:%M:%SZ)
if ! python3 - "$RUN_DIR/run.json" <<'PY'
import json,sys
sys.exit(0 if json.load(open(sys.argv[1])).get('operation')=='policy_compare' else 2)
PY
then echo 'Policy comparison requires a labelled policy_compare run' >&2; exit 2; fi
code=0
bash editorial/select_items.sh "$RUN_DIR" < "$RUN_DIR/eligible.jsonl" > "$RUN_DIR/decisions.jsonl" || code=$?
if [ "$code" -eq 0 ]; then python3 editorial/policy_diff_helper.py "$RUN_DIR" > "$RUN_DIR/policy_diff_result.json" || code=$?; fi
python3 lib/receipt_helper.py "$RUN_DIR" policy-compare "$started" "$code" "$RUN_DIR/eligible.jsonl" "$RUN_DIR/decisions.jsonl"
exit "$code"
