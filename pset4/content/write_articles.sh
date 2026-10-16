#!/usr/bin/env bash
set -euo pipefail
# Generate article bodies; code appends source notes from validated references.
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
exec python3 content/articles_helper.py "$@"
