#!/usr/bin/env bash
set -euo pipefail
# Collect, resume, package, or create a labelled replay; save summary last.
ROOT=$(cd "$(dirname "$0")" && pwd)
cd "$ROOT"
resume_run=''
from_stage=''
mode=live
source_run=''
if [ "$#" -eq 4 ] && [ "$1" = '--resume' ] && [ "$3" = '--from' ]; then
    mode=resume
    resume_run="$2"
    from_stage="$4"
    case "$from_stage" in
        select_items|create_briefs|write_content|check_content) ;;
        *) echo 'Invalid --from stage; use select_items, create_briefs, write_content or check_content' >&2; exit 2 ;;
    esac
elif [ "$#" -eq 2 ]; then
    source_run="$2"
    case "$1" in
        --package) mode=package ;;
        --replay) mode=replay ;;
        --policy-compare) mode=policy-compare ;;
        *) echo 'Invalid run option' >&2; exit 2 ;;
    esac
elif [ "$#" -ne 0 ]; then
    echo 'usage: bash run.sh | --resume RUN_DIR --from STAGE | --package RUN_DIR | --replay RUN_DIR | --policy-compare RUN_DIR' >&2
    exit 2
fi
if [ -f .env ]; then
    set +x
    set -a
    if ! . ./.env >/dev/null 2>&1; then
        echo 'Could not load .env; no values displayed' >&2
        exit 2
    fi
    set +a
fi
required_tools=(python3 jq sqlite3)
if [ "$mode" = live ]; then required_tools+=(yt-dlp ffmpeg); fi
for tool in "${required_tools[@]}"; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "Missing tool: $tool" >&2
        exit 2
    fi
done
export RUN_DIR
receipt_options=()
run_stage=run
if [ "$mode" = package ]; then
    RUN_DIR=$(python3 run_helper.py resume "$source_run")
    run_stage=run-package
elif [ "$mode" = replay ] || [ "$mode" = policy-compare ]; then
    RUN_DIR=$(python3 run_helper.py "$mode" "$source_run")
    run_stage="run-$mode"
elif [ -n "$resume_run" ]; then
    RUN_DIR=$(python3 run_helper.py resume "$resume_run")
    run_stage=run-resume
    receipt_options=(--resumed-from "$from_stage" --reason "User-requested resume from $from_stage using saved upstream artifacts.")
else
    RUN_DIR=$(python3 run_helper.py setup)
fi
started=$(date -u +%Y-%m-%dT%H:%M:%SZ)
status=0
failures=()
collection_status=0
series_status=0
if [ "$mode" = package ]; then
    bash review/check_content.sh "$RUN_DIR" > "$RUN_DIR/review.json" || status=$?
    if [ "$status" -eq 0 ]; then bash publishing/prepare_package.sh "$RUN_DIR" > "$RUN_DIR/package_result.json" || status=$?; fi
    if [ "$status" -ne 0 ]; then failures+=("prepare-package=$status"); fi
elif [ "$mode" = replay ]; then
    bash workflows/replay_sources.sh "$RUN_DIR" || status=$?
    if [ "$status" -ne 0 ]; then failures+=("replay-sources=$status"); fi
elif [ "$mode" = policy-compare ]; then
    bash workflows/compare_policy.sh "$RUN_DIR" || status=$?
    if [ "$status" -ne 0 ]; then failures+=("policy-compare=$status"); fi
elif [ -n "$resume_run" ]; then
    bash workflows/create_series.sh "$RUN_DIR" --from "$from_stage" || series_status=$?
    if [ "$series_status" -ne 0 ]; then failures+=("create-series=$series_status"); status=1; fi
else
    bash data/store.sh init || status=$?
    if [ "$status" -eq 0 ]; then
        bash workflows/collect_sources.sh "$RUN_DIR" || collection_status=$?
        if [ "$collection_status" -ne 0 ]; then failures+=("collect-sources=$collection_status"); fi
        # Partial collection may still provide enough genuine evidence for a series.
        bash workflows/create_series.sh "$RUN_DIR" || series_status=$?
        if [ "$series_status" -ne 0 ]; then failures+=("create-series=$series_status"); fi
        if [ "$collection_status" -ne 0 ] || [ "$series_status" -ne 0 ]; then status=1; fi
    else
        failures+=("store-init=$status")
    fi
fi
python3 lib/receipt_helper.py "$RUN_DIR" "$run_stage" "$started" "$status" - "$RUN_DIR/eligible.jsonl" ${failures[@]+"${failures[@]}"} ${receipt_options[@]+"${receipt_options[@]}"}
summary_status=0
bash reporting/summarize_run.sh "$RUN_DIR" > "$RUN_DIR/summary.json" || summary_status=$?
cat "$RUN_DIR/summary.json"
if [ "$summary_status" -ne 0 ]; then exit "$summary_status"; fi
if [ "$status" -ne 0 ]; then exit "$status"; fi
# Coverage deficits are operationally incomplete even when all tools ran.
if ! jq -e '.coverage.passed' "$RUN_DIR/summary.json" >/dev/null; then exit 1; fi
