#!/usr/bin/env bash
# Prepare compact immutable assets; publishing is a separate explicit command.
set -euo pipefail
ARCH=${1:?architecture required}
STORAGE=${CHROMAX_STORAGE:-/Volumes/Models/Chromax}
SOURCE=$STORAGE/artifacts/$ARCH
DEST=$STORAGE/release/$ARCH
mkdir -p "$DEST"
for name in chromax.img rootfs.ext4; do
    test -f "$SOURCE/$name"
    zstd -T2 -10 -f "$SOURCE/$name" -o "$DEST/chromax-0.1.0-$ARCH-$name.zst"
done
for name in Image bzImage buildroot.config packages.json sbom.cdx.json chromax-source.tar.gz buildroot-2026.08.1.tar.xz legal-info.tar; do
    if [ -f "$SOURCE/$name" ]; then cp "$SOURCE/$name" "$DEST/$name"; fi
done
(
    cd "$DEST"
    find . -maxdepth 1 -type f ! -name SHA256SUMS ! -name '*.sig' -exec sha256sum '{}' \; | sort > SHA256SUMS
    sha256sum "$SOURCE/chromax.img" "$SOURCE/rootfs.ext4" > UNCOMPRESSED_SHA256SUMS
)
