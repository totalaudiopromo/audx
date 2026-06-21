#!/usr/bin/env bash
# Copy the pure-Python audx modules the browser playground loads into site/audx_web/.
# These are the REAL DSL parser + synth kit, so the in-browser sound matches the CLI.
# Run after editing src/audx/{synth,pattern}.py. CI (pages.yml) also runs this on deploy.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p site/audx_web
cp src/audx/synth.py site/audx_web/synth.py
cp src/audx/pattern.py site/audx_web/pattern.py
echo "synced synth.py + pattern.py -> site/audx_web/"
