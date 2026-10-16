#!/usr/bin/env bash
set -euo pipefail
# Apply the snapshotted policy with one real, validated editorial decision per item.
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
exec python3 editorial/select_helper.py "$@"
