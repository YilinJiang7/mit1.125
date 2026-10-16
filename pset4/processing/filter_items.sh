#!/usr/bin/env bash
set -euo pipefail
# Mechanically apply the inclusive UTC window; write exclusions beside the run.
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
exec python3 processing/filter_helper.py "$@"
