#!/usr/bin/env bash
set -euo pipefail
# Generate video narration and scene directions using the same validated briefs.
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
exec python3 content/scripts_helper.py "$@"
