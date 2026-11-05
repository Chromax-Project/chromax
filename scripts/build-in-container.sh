#!/usr/bin/env bash
set -euo pipefail
if [ "${CHROMAX_REUSE_WORKSPACE:-0}" = 1 ]; then
    mountpoint -q /work || { echo 'Expected an already mounted build filesystem' >&2; exit 1; }
else
    mount -o loop /storage/build.ext4 /work
    trap 'sync; umount /work' EXIT
fi
mkdir -p /work/source /work/output /work/repo /work/dl
rsync -a --delete --exclude=.git --exclude=__pycache__ --exclude=.pytest_cache \
    --exclude=.env --exclude='*.pem' --exclude='*.gguf' --exclude=output \
    --exclude=dist --exclude=.cache /repo/ /work/repo/
VERSION=2026.08.1
ARCHIVE=/storage/sources/buildroot-$VERSION.tar.xz
if [ ! -f "$ARCHIVE" ]; then curl -fL --retry 3 "https://buildroot.org/downloads/buildroot-$VERSION.tar.xz" -o "$ARCHIVE"; fi
echo "34fb7bea8a213ffde39cc02e61703391560f26e0850f03138c722d0b09880f2b  $ARCHIVE" | sha256sum -c -
if [ ! -d "/work/source/buildroot-$VERSION" ]; then tar -xJf "$ARCHIVE" -C /work/source; fi
BR=/work/source/buildroot-$VERSION
OUT=/work/output/$CHROMAX_ARCH
KERNEL_ARCHIVE=/work/dl/linux/linux-6.18.60.tar.xz
if [ -f "$KERNEL_ARCHIVE" ]; then
    echo "3c2f44ef6acc021a7ad444d9a2e6ec1ef488ff09368793d0004a6080f69d621e  $KERNEL_ARCHIVE" | sha256sum -c -
fi
chown -R builder:builder /work
sudo -u builder make -C "$BR" O="$OUT" BR2_EXTERNAL=/work/repo BR2_DL_DIR=/work/dl "chromax_${CHROMAX_ARCH}_defconfig"
# Local source packages are stamp-based; never retain an old management tool
# merely because the upstream toolchain is already built.
sudo -u builder make -C "$BR" O="$OUT" BR2_EXTERNAL=/work/repo BR2_DL_DIR=/work/dl chromax-dirclean
BUSYBOX_HASH=$(sha256sum /work/repo/board/chromax/busybox.fragment | cut -d' ' -f1)
if [ "$(cat "$OUT/.chromax-busybox-hash" 2>/dev/null || true)" != "$BUSYBOX_HASH" ]; then
    sudo -u builder make -C "$BR" O="$OUT" BR2_EXTERNAL=/work/repo BR2_DL_DIR=/work/dl busybox-dirclean
    echo "$BUSYBOX_HASH" > "$OUT/.chromax-busybox-hash"
fi
sudo -u builder make -C "$BR" O="$OUT" BR2_EXTERNAL=/work/repo BR2_DL_DIR=/work/dl -j"$CHROMAX_JOBS"
echo "3c2f44ef6acc021a7ad444d9a2e6ec1ef488ff09368793d0004a6080f69d621e  $KERNEL_ARCHIVE" | sha256sum -c -
mkdir -p "/storage/artifacts/$CHROMAX_ARCH"
cp -a "$OUT/images/." "/storage/artifacts/$CHROMAX_ARCH/"
tar -C /work/repo -czf "/storage/artifacts/$CHROMAX_ARCH/chromax-source.tar.gz" .
cp "$ARCHIVE" "/storage/artifacts/$CHROMAX_ARCH/buildroot-$VERSION.tar.xz"
cp "$OUT/.config" "/storage/artifacts/$CHROMAX_ARCH/buildroot.config"
sudo -u builder make -s -C "$BR" O="$OUT" BR2_EXTERNAL=/work/repo BR2_DL_DIR=/work/dl show-info > "/storage/artifacts/$CHROMAX_ARCH/packages.json"
BR2_DL_DIR=/work/dl python3 "$BR/utils/generate-cyclonedx" < "/storage/artifacts/$CHROMAX_ARCH/packages.json" > "/storage/artifacts/$CHROMAX_ARCH/sbom.cdx.json"
sudo -u builder make -C "$BR" O="$OUT" BR2_EXTERNAL=/work/repo BR2_DL_DIR=/work/dl legal-info
tar -C "$OUT" -cf "/storage/artifacts/$CHROMAX_ARCH/legal-info.tar" legal-info
(
    cd "/storage/artifacts/$CHROMAX_ARCH"
    find . -maxdepth 1 -type f ! -name SHA256SUMS -exec sha256sum '{}' \; | sort > SHA256SUMS
)
