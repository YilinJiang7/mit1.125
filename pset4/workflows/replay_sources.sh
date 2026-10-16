#!/usr/bin/env bash
set -euo pipefail
# Re-feed saved candidates through offline extraction and a read-only store.
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
if [ "$#" -ne 1 ] || [ ! -f "$1/run.json" ]; then echo 'usage: replay_sources.sh RUN_DIR' >&2; exit 2; fi
export RUN_DIR="$1"
started=$(date -u +%Y-%m-%dT%H:%M:%SZ)
if ! python3 - "$RUN_DIR/run.json" <<'PY'
import json,sys
sys.exit(0 if json.load(open(sys.argv[1])).get('operation')=='collection_replay' else 2)
PY
then echo 'Replay workflow requires a labelled collection_replay run' >&2; exit 2; fi
fail() {
    echo "Replay stopped at $1; no source fetches or store mutations were permitted." >&2
    python3 lib/receipt_helper.py "$RUN_DIR" replay-sources "$started" 1 "$RUN_DIR/candidates.jsonl" - "$1=1"
    exit 1
}
bash data/store.sh stats > "$RUN_DIR/store_before.json" || fail store-before
bash processing/extract_content.sh "$RUN_DIR" < "$RUN_DIR/candidates.jsonl" > "$RUN_DIR/items.jsonl" || fail offline-extraction
bash data/store.sh upsert "$RUN_DIR" < "$RUN_DIR/items.jsonl" > "$RUN_DIR/changes.jsonl" || fail read-only-upsert
bash data/store.sh list > "$RUN_DIR/corpus.jsonl" || fail store-list
bash processing/filter_items.sh "$RUN_DIR" < "$RUN_DIR/corpus.jsonl" > "$RUN_DIR/eligible.jsonl" || fail filter
bash data/store.sh stats > "$RUN_DIR/store_after.json" || fail store-after
python3 - "$RUN_DIR" <<'PY' || fail verification
import json,sys
from pathlib import Path
run=Path(sys.argv[1]);load=lambda name:json.loads((run/name).read_text())
changes=[json.loads(line) for line in (run/'changes.jsonl').read_text().splitlines() if line.strip()]
items=[json.loads(line) for line in (run/'items.jsonl').read_text().splitlines() if line.strip()]
passed=load('store_before.json')==load('store_after.json') and len(changes)==len(items) and all(r['change']=='unchanged' for r in changes)
result={'passed':passed,'network_disabled':True,'read_only_store':True,'unchanged':len(changes),
        'before':load('store_before.json'),'after':load('store_after.json')}
(run/'replay_check.json').write_text(json.dumps(result,indent=2)+'\n')
sys.exit(0 if passed else 1)
PY
python3 lib/receipt_helper.py "$RUN_DIR" replay-sources "$started" 0 "$RUN_DIR/candidates.jsonl" "$RUN_DIR/changes.jsonl"
