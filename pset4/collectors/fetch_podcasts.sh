#!/usr/bin/env bash
set -euo pipefail
# Discover podcast episodes and audio enclosures from the source snapshot.
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
exec python3 collectors/podcasts_helper.py "$@"
