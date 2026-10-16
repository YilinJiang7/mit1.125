#!/usr/bin/env bash
set -euo pipefail
# Coordinate discovery, extraction, storage and freshness; preserve partial results.
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
if [ "$#" -ne 1 ] || [ ! -f "$1/run.json" ]; then
    echo 'usage: collect_sources.sh RUN_DIR' >&2
    exit 2
fi
export RUN_DIR="$1"
started=$(date -u +%Y-%m-%dT%H:%M:%SZ)
mkdir -p "$RUN_DIR/candidates"
failures=()
status=0
for kind in feeds youtube podcasts; do
    code=0
    bash "collectors/fetch_${kind}.sh" "$RUN_DIR" > "$RUN_DIR/candidates/$kind.jsonl" || code=$?
    if [ "$code" -ne 0 ]; then
        failures+=("fetch-$kind=$code")
        status=1
    fi
done
cat "$RUN_DIR/candidates/feeds.jsonl" "$RUN_DIR/candidates/youtube.jsonl" "$RUN_DIR/candidates/podcasts.jsonl" > "$RUN_DIR/candidates.jsonl"
code=0
# A real pipe feeds candidate records to the independently runnable extractor.
cat "$RUN_DIR/candidates.jsonl" | bash processing/extract_content.sh "$RUN_DIR" > "$RUN_DIR/items.jsonl" || code=$?
if [ "$code" -ne 0 ]; then
    failures+=("extract-content=$code")
    status=1
fi
code=0
bash data/store.sh upsert "$RUN_DIR" < "$RUN_DIR/items.jsonl" > "$RUN_DIR/changes.jsonl" || code=$?
if [ "$code" -ne 0 ]; then
    failures+=("store-upsert=$code")
    status=1
else
    code=0
    bash data/store.sh list > "$RUN_DIR/corpus.jsonl" || code=$?
    if [ "$code" -ne 0 ]; then
        failures+=("store-list=$code")
        status=1
    else
        code=0
        bash processing/filter_items.sh "$RUN_DIR" < "$RUN_DIR/corpus.jsonl" > "$RUN_DIR/eligible.jsonl" || code=$?
        if [ "$code" -ne 0 ]; then
            failures+=("filter-items=$code")
            status=1
        fi
    fi
fi
python3 lib/receipt_helper.py "$RUN_DIR" collect-sources "$started" "$status" "$RUN_DIR/candidates.jsonl" "$RUN_DIR/eligible.jsonl" ${failures[@]+"${failures[@]}"}
exit "$status"
