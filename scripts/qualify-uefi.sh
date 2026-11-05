#!/usr/bin/env bash
set -euo pipefail
ARCH=${1:?architecture required}
case "$ARCH" in aarch64|x86_64) ;; *) exit 2;; esac
IMAGES=/storage/artifacts/$ARCH
BASE=/storage/qualification/$ARCH
WORK=$BASE/uefi
mkdir -p "$WORK/evidence" /mnt/qualification
test -f "$BASE/fixtures/publisher-public.pem"
# Installation writes only a fresh file-backed loop device. No physical disks.
truncate -s "$(stat -c %s "$IMAGES/chromax.img")" "$WORK/installed.img"
LOOP=$(losetup --find --show "$WORK/installed.img")
trap 'losetup -d "$LOOP" 2>/dev/null || true' EXIT
CHECKSUM=$(sha256sum "$IMAGES/chromax.img" | cut -d' ' -f1)
PYTHONPATH=/repo/src python3 -m chromax.installer "$IMAGES/chromax.img" "$LOOP" \
    --sha256 "$CHECKSUM" --confirm "$LOOP" | tee "$WORK/evidence/installer.log"
losetup -d "$LOOP"
trap - EXIT
OFFSET=$(sfdisk --json "$WORK/installed.img" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["partitiontable"]["partitions"][1]["start"]*d["partitiontable"]["sectorsize"])')
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
