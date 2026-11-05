#!/usr/bin/env bash
# Run inside the privileged builder container, with /storage and /repo mounted.
set -euo pipefail
ARCH=${1:?architecture required}
case "$ARCH" in aarch64|x86_64) ;; *) exit 2;; esac
IMAGES=/storage/artifacts/$ARCH
WORK=/storage/qualification/$ARCH
if [ -f "$WORK/evidence-direct/qualification.json" ]; then
    mv "$WORK/evidence-direct" "$WORK/evidence-direct-$(date -u +%Y%m%dT%H%M%SZ)"
fi
mkdir -p "$WORK/fixtures" "$WORK/evidence-direct"
cp --sparse=always "$IMAGES/rootfs.ext4" "$WORK/rootfs.ext4"
if [ ! -f "$WORK/id_ed25519" ]; then ssh-keygen -q -t ed25519 -N '' -f "$WORK/id_ed25519"; fi
cp "$WORK/id_ed25519.pub" "$WORK/fixtures/"
openssl genpkey -algorithm ED25519 -out "$WORK/publisher-private.pem"
openssl pkey -in "$WORK/publisher-private.pem" -pubout -out "$WORK/fixtures/publisher-public.pem"
for VERSION in 1.0.0 2.0.0; do
    mkdir -p "$WORK/hello-$VERSION"
    printf '#!/bin/sh\nprintf "hello-%s\\n"\n' "$VERSION" > "$WORK/hello-$VERSION/hello"
    chmod 0755 "$WORK/hello-$VERSION/hello"
    PYTHONPATH=/repo/src python3 -m chromax.cli package build "$WORK/hello-$VERSION" "$WORK/fixtures/hello-$VERSION.cxpk" \
        --name hello --version "$VERSION" --architecture all --entrypoint hello
    openssl pkeyutl -sign -inkey "$WORK/publisher-private.pem" -rawin \
        -in "$WORK/fixtures/hello-$VERSION.cxpk" -out "$WORK/fixtures/hello-$VERSION.cxpk.sig"
done
if [ -n "${CHROMAX_TEST_MODEL:-}" ]; then cp "$CHROMAX_TEST_MODEL" "$WORK/fixtures/model.gguf"; fi
mkdir -p /mnt/qualification
mount -o loop "$WORK/rootfs.ext4" /mnt/qualification
trap 'umount /mnt/qualification' EXIT
mkdir -p /mnt/qualification/home/chromax/qualification
cp "$WORK/fixtures/"* /mnt/qualification/home/chromax/qualification/
chown -R 1000:1000 /mnt/qualification/home/chromax/qualification
sync
umount /mnt/qualification
trap - EXIT
MODEL_ARGS=()
if [ -n "${CHROMAX_TEST_MODEL:-}" ]; then MODEL_ARGS=(--model-sha256 "$(sha256sum "$CHROMAX_TEST_MODEL" | cut -d' ' -f1)"); fi
PYTHONPATH=/repo/src python3 /repo/scripts/qualify.py --architecture "$ARCH" --images "$IMAGES" \
    --rootfs "$WORK/rootfs.ext4" --evidence "$WORK/evidence-direct" --ssh-key "$WORK/id_ed25519" "${MODEL_ARGS[@]}"
