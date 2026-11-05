#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
ARCH=${1:-aarch64}
case "$ARCH" in aarch64|x86_64) ;; *) echo 'Architecture must be aarch64 or x86_64' >&2; exit 2;; esac
STORAGE=${CHROMAX_STORAGE:-/Volumes/Models/Chromax}
mkdir -p "$STORAGE/sources" "$STORAGE/artifacts" "$STORAGE/logs"
docker build -t chromax-builder:2026.11 -f "$ROOT/scripts/Dockerfile" "$ROOT"
if [ ! -f "$STORAGE/build.ext4" ]; then
  docker run --rm -v "$STORAGE:/storage" chromax-builder:2026.11 \
    sh -c 'truncate -s 96G /storage/build.ext4 && mkfs.ext4 -F -m 0 /storage/build.ext4'
fi
docker run --rm --privileged --name "chromax-build-$ARCH" \
  --memory=7g --cpus=10 -v "$STORAGE:/storage" -v "$ROOT:/repo:ro" \
  -e "CHROMAX_ARCH=$ARCH" -e "CHROMAX_JOBS=${CHROMAX_JOBS:-6}" \
  chromax-builder:2026.11 /repo/scripts/build-in-container.sh
