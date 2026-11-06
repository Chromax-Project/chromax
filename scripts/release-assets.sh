#!/usr/bin/env bash
# Prepare compact immutable assets; publishing is a separate explicit command.
set -euo pipefail
ARCH=${1:?architecture required}
STORAGE=${CHROMAX_STORAGE:-/Volumes/Models/Chromax}
SOURCE=$STORAGE/artifacts/$ARCH
DEST=$STORAGE/release/$ARCH
PREFIX=chromax-0.1.0-$ARCH
mkdir -p "$DEST"
: > "$DEST/$PREFIX-UNCOMPRESSED_SHA256SUMS"
for name in chromax.img rootfs.ext4; do
    test -f "$SOURCE/$name"
    if [ "${CHROMAX_REUSE_COMPRESSED:-0}" != 1 ] || [ ! -f "$DEST/$PREFIX-$name.zst" ]; then
        zstd -T2 -10 -f "$SOURCE/$name" -o "$DEST/$PREFIX-$name.zst"
    fi
    # Verify the compressed payload against the build's measured image hash.
    # Hashing the small compressed file's decoded stream avoids rereading many
    # gigabytes of zero-filled ext4 space from slow external storage.
    expected_name=$name
    if [ "$name" = rootfs.ext4 ]; then expected_name=rootfs.ext2; fi
    expected=$(awk -v name="./$expected_name" '$2 == name { print $1 }' "$SOURCE/SHA256SUMS")
    test "${#expected}" = 64
    actual=$(zstd -qdc "$DEST/$PREFIX-$name.zst" | sha256sum | cut -d' ' -f1)
    test "$actual" = "$expected" || { echo "Compressed image verification failed: $name" >&2; exit 1; }
    printf '%s  %s\n' "$actual" "$name" >> "$DEST/$PREFIX-UNCOMPRESSED_SHA256SUMS"
done
for name in Image bzImage buildroot.config linux.config busybox.config packages.json sbom.cdx.json qualification.json build.json chromax-source.tar.gz buildroot-2026.08.1.tar.xz legal-info.tar; do
    if [ -f "$SOURCE/$name" ]; then
        # APFS clones keep source/license archives cheap on macOS. Other hosts
        # fall back to an ordinary copy without changing the resulting bytes.
        cp -c "$SOURCE/$name" "$DEST/$PREFIX-$name" 2>/dev/null || cp "$SOURCE/$name" "$DEST/$PREFIX-$name"
    fi
done
if [ -f "$STORAGE/keys/release.pub" ]; then cp "$STORAGE/keys/release.pub" "$DEST/$PREFIX-release.pub"; fi
(
    cd "$DEST"
    find . -maxdepth 1 -type f ! -name '*SHA256SUMS' ! -name '*.sig' -exec sha256sum '{}' \; | sort > "$PREFIX-SHA256SUMS"
    sha256sum "$PREFIX-UNCOMPRESSED_SHA256SUMS" >> "$PREFIX-SHA256SUMS"
    if [ -f "$STORAGE/keys/release-private.pem" ]; then
        openssl pkeyutl -sign -inkey "$STORAGE/keys/release-private.pem" -rawin \
            -in "$PREFIX-SHA256SUMS" -out "$PREFIX-SHA256SUMS.sig"
    fi
)
