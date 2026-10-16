#!/usr/bin/env bash
set -euo pipefail
# Create three arguments using accepted evidence; validate and allow one repair.
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
exec python3 editorial/briefs_helper.py "$@"
