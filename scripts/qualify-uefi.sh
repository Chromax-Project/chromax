#!/usr/bin/env bash
set -euo pipefail
ARCH=${1:?architecture required}
case "$ARCH" in aarch64|x86_64) ;; *) exit 2;; esac
IMAGES=${CHROMAX_IMAGES:-/storage/artifacts/$ARCH}
BASE=/storage/qualification/$ARCH
WORK=$BASE/uefi
mkdir -p "$WORK/evidence" /mnt/qualification
test -f "$BASE/fixtures/publisher-public.pem"
# Installation writes only a fresh file-backed loop device. No physical disks.
if [ "${CHROMAX_REUSE_INSTALLED:-0}" != 1 ]; then
    truncate -s "$(stat -c %s "$IMAGES/chromax.img")" "$WORK/installed.img"
    LOOP=$(losetup --find --show "$WORK/installed.img")
    trap 'losetup -d "$LOOP" 2>/dev/null || true' EXIT
    CHECKSUM=$(sha256sum "$IMAGES/chromax.img" | cut -d' ' -f1)
    PYTHONPATH=/repo/src python3 -u -m chromax.installer "$IMAGES/chromax.img" "$LOOP" \
        --sha256 "$CHECKSUM" --confirm "$LOOP" | tee "$WORK/evidence/installer.log"
    losetup -d "$LOOP"
    trap - EXIT
else
    test -f "$WORK/installed.img"
    grep -q 'Installed and verified' "$WORK/evidence/installer.log"
    echo 'Resuming from the prior readback-verified installation.'
fi
OFFSET=$(parted -m -s "$WORK/installed.img" unit B print | awk -F: '$1 == "2" { sub(/B$/, "", $2); print $2 }')
test -n "$OFFSET"
mount -o "loop,offset=$OFFSET" "$WORK/installed.img" /mnt/qualification
trap 'umount /mnt/qualification' EXIT
mkdir -p /mnt/qualification/home/chromax/qualification
for FILE in "$BASE/fixtures/"*; do
    if [ "$(basename "$FILE")" != model.gguf ]; then cp "$FILE" /mnt/qualification/home/chromax/qualification/; fi
done
chown -R 1000:1000 /mnt/qualification/home/chromax/qualification
sync
umount /mnt/qualification
trap - EXIT
PYTHONPATH=/repo/src python3 /repo/scripts/qualify.py --architecture "$ARCH" --images "$IMAGES" \
    --rootfs "$WORK/installed.img" --evidence "$WORK/evidence" --ssh-key "$BASE/id_ed25519" --uefi
