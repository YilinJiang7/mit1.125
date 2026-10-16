#!/usr/bin/env bash
set -euo pipefail
# Save editorial artifacts in order; --from reuses saved upstream artifacts.
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
if [ "$#" -ne 1 ] && [ "$#" -ne 3 ]; then
    echo 'usage: create_series.sh RUN_DIR [--from select_items|create_briefs|write_content|check_content]' >&2
    exit 2
fi
if [ ! -f "$1/run.json" ]; then echo 'RUN_DIR must contain run.json' >&2; exit 2; fi
from_stage=select_items
receipt_options=()
if [ "$#" -eq 3 ]; then
    if [ "$2" != '--from' ]; then echo 'Expected --from STAGE' >&2; exit 2; fi
    from_stage="$3"
    receipt_options=(--resumed-from "$from_stage" --reason "User-requested resume from $from_stage using saved upstream artifacts.")
fi
case "$from_stage" in
    select_items) start_at=0 ;;
    create_briefs) start_at=1 ;;
    write_content) start_at=2 ;;
    check_content) start_at=3 ;;
    *) echo 'Invalid --from stage; use select_items, create_briefs, write_content or check_content' >&2; exit 2 ;;
esac
export RUN_DIR="$1"
started=$(date -u +%Y-%m-%dT%H:%M:%SZ)
finish_failure() {
    echo "Series stopped at $1; inspect its receipt. No unsupported content substituted." >&2
    python3 lib/receipt_helper.py "$RUN_DIR" create-series "$started" 1 "$RUN_DIR/eligible.jsonl" - "$1=$2" ${receipt_options[@]+"${receipt_options[@]}"}
    exit 1
}
if [ ! -s "$RUN_DIR/eligible.jsonl" ]; then finish_failure eligible-evidence 1; fi
if ! python3 - "$RUN_DIR/eligible.jsonl" <<'PY'
import json,sys
rows=[json.loads(line) for line in open(sys.argv[1]) if line.strip()]
rows={row['item_id']:row for row in rows if not row.get('duplicate_of')}.values()
counts={kind:sum(row['kind']==kind for row in rows) for kind in ['feed','youtube','podcast']}
passed=len(rows)>=12 and len({row['publisher_id'] for row in rows})>=6 and all(count>=2 for count in counts.values())
if not passed:print('Insufficient eligible evidence: require 12 distinct items, 6 publishers, 2 per kind',file=sys.stderr)
sys.exit(0 if passed else 1)
PY
then finish_failure eligible-coverage 1; fi
if [ "$start_at" -ge 1 ] && [ ! -s "$RUN_DIR/decisions.jsonl" ]; then finish_failure saved-decisions 1; fi
if [ "$start_at" -ge 2 ] && [ ! -s "$RUN_DIR/briefs.jsonl" ]; then finish_failure saved-briefs 1; fi
if [ "$start_at" -le 0 ]; then
    code=0
    bash editorial/select_items.sh "$RUN_DIR" < "$RUN_DIR/eligible.jsonl" > "$RUN_DIR/decisions.jsonl" || code=$?
    if [ "$code" -ne 0 ]; then finish_failure select-items "$code"; fi
fi
if [ "$start_at" -le 1 ]; then
    code=0
    bash editorial/create_briefs.sh "$RUN_DIR" < "$RUN_DIR/decisions.jsonl" > "$RUN_DIR/briefs.jsonl" || code=$?
    if [ "$code" -ne 0 ]; then finish_failure create-briefs "$code"; fi
fi
if [ "$start_at" -le 2 ]; then
    code=0
    bash content/write_articles.sh "$RUN_DIR" < "$RUN_DIR/briefs.jsonl" > "$RUN_DIR/articles.jsonl" || code=$?
    if [ "$code" -ne 0 ]; then finish_failure write-articles "$code"; fi
    code=0
    bash content/write_video_scripts.sh "$RUN_DIR" < "$RUN_DIR/briefs.jsonl" > "$RUN_DIR/video_scripts.jsonl" || code=$?
    if [ "$code" -ne 0 ]; then finish_failure write-video-scripts "$code"; fi
fi
code=0
bash review/check_content.sh "$RUN_DIR" > "$RUN_DIR/review.json" || code=$?
if [ "$code" -ne 0 ]; then finish_failure check-content "$code"; fi
if ! jq -e '.passed' "$RUN_DIR/review.json" >/dev/null; then finish_failure content-review 1; fi
python3 lib/receipt_helper.py "$RUN_DIR" create-series "$started" 0 "$RUN_DIR/eligible.jsonl" "$RUN_DIR/briefs.jsonl" ${receipt_options[@]+"${receipt_options[@]}"}
