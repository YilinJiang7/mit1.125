#!/usr/bin/env bash
set -euo pipefail
# Report saved artifacts, incomplete stages, distinct evidence coverage and costs.
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
exec python3 reporting/summary_helper.py "$@"
