#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
docker run --rm --network=none --memory=512m --cpus=2 \
    -v "$ROOT:/repo:ro" -e PYTHONPATH=/repo/src \
    chromax-builder:2026.11 python3 -m unittest discover -s /repo/tests -v
