#!/usr/bin/env bash
set -euo pipefail
# Own the persistent evidence index; helpers elsewhere use this interface.
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
exec python3 data/store_helper.py "$@"
