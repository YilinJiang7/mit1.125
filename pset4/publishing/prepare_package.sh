#!/usr/bin/env bash
set -euo pipefail
# Package only currently assessed, explicitly approved material.
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
exec python3 publishing/package_helper.py "$@"
