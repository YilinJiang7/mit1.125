#!/usr/bin/env bash
set -euo pipefail
# Discover written articles from the run's snapshotted RSS/Atom sources.
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
exec python3 collectors/feeds_helper.py "$@"
