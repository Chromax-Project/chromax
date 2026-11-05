#!/usr/bin/env bash
set -euo pipefail
mount -o loop /storage/build.ext4 /work
trap 'sync; umount /work' EXIT
mkdir -p /work/source /work/output /work/repo /work/dl
rsync -a --delete --exclude=.git /repo/ /work/repo/
VERSION=2026.08.1
ARCHIVE=/storage/sources/buildroot-$VERSION.tar.xz
if [ ! -f "$ARCHIVE" ]; then curl -fL --retry 3 "https://buildroot.org/downloads/buildroot-$VERSION.tar.xz" -o "$ARCHIVE"; fi
echo "34fb7bea8a213ffde39cc02e61703391560f26e0850f03138c722d0b09880f2b  $ARCHIVE" | sha256sum -c -
if [ ! -d "/work/source/buildroot-$VERSION" ]; then tar -xJf "$ARCHIVE" -C /work/source; fi
BR=/work/source/buildroot-$VERSION
OUT=/work/output/$CHROMAX_ARCH
chown -R builder:builder /work
sudo -u builder make -C "$BR" O="$OUT" BR2_EXTERNAL=/work/repo BR2_DL_DIR=/work/dl "chromax_${CHROMAX_ARCH}_defconfig"
sudo -u builder make -C "$BR" O="$OUT" BR2_EXTERNAL=/work/repo BR2_DL_DIR=/work/dl -j"$CHROMAX_JOBS"
mkdir -p "/storage/artifacts/$CHROMAX_ARCH"
cp -a "$OUT/images/." "/storage/artifacts/$CHROMAX_ARCH/"
cp "$OUT/.config" "/storage/artifacts/$CHROMAX_ARCH/buildroot.config"
sudo -u builder make -C "$BR" O="$OUT" BR2_EXTERNAL=/work/repo BR2_DL_DIR=/work/dl legal-info
tar -C "$OUT" -cf "/storage/artifacts/$CHROMAX_ARCH/legal-info.tar" legal-info
find "/storage/artifacts/$CHROMAX_ARCH" -maxdepth 1 -type f ! -name SHA256SUMS -exec sha256sum '{}' \; > "/storage/artifacts/$CHROMAX_ARCH/SHA256SUMS"
