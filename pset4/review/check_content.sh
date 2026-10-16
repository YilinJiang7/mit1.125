#!/usr/bin/env bash
set -euo pipefail
# Assess saved drafts and evidence; a completed assessment exits 0 even if failed.
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
exec python3 review/check_helper.py "$@"
