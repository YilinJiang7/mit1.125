#!/usr/bin/env bash
set -euo pipefail
# Resolve YouTube identities and discover dated videos, using channel RSS.
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
exec python3 collectors/youtube_helper.py "$@"
