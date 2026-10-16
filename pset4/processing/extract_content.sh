#!/usr/bin/env bash
set -euo pipefail
# Retrieve substantive text or timestamped media transcripts into immutable assets.
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
exec python3 processing/extract_helper.py "$@"
