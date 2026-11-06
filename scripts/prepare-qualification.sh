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
BUILD=(env PYTHONPATH=/repo/src)
if [ -n "${SUDO_USER:-}" ] && [ "$SUDO_USER" != root ]; then
    # Keep fixture construction unprivileged on native Linux hosts. The
    # surrounding mount/provision operations still require the root test driver.
    chown "$SUDO_USER" "$WORK" "$WORK/fixtures"
    BUILD=(sudo -u "$SUDO_USER" env PYTHONPATH=/repo/src)
fi
if [ "${CHROMAX_PREPARED_ROOTFS:-0}" = 1 ]; then
    test -f "$WORK/rootfs.ext4"
else
    cp --sparse=always "$IMAGES/rootfs.ext4" "$WORK/rootfs.ext4"
fi
if [ ! -f "$WORK/id_ed25519" ]; then ssh-keygen -q -t ed25519 -N '' -f "$WORK/id_ed25519"; fi
cp "$WORK/id_ed25519.pub" "$WORK/fixtures/"
openssl genpkey -algorithm ED25519 -out "$WORK/publisher-private.pem"
openssl pkey -in "$WORK/publisher-private.pem" -pubout -out "$WORK/fixtures/publisher-public.pem"
for VERSION in 1.0.0 2.0.0; do
    mkdir -p "$WORK/hello-$VERSION"
    printf '#!/bin/sh\nprintf "hello-%s\\n"\n' "$VERSION" > "$WORK/hello-$VERSION/hello"
    chmod 0755 "$WORK/hello-$VERSION/hello"
    "${BUILD[@]}" python3 -m chromax.cli package build "$WORK/hello-$VERSION" "$WORK/fixtures/hello-$VERSION.cxpk" \
        --name hello --version "$VERSION" --architecture all --entrypoint hello
    openssl pkeyutl -sign -inkey "$WORK/publisher-private.pem" -rawin \
        -in "$WORK/fixtures/hello-$VERSION.cxpk" -out "$WORK/fixtures/hello-$VERSION.cxpk.sig"
done
if [ -n "${CHROMAX_TEST_MODEL:-}" ]; then
    ln -f "$CHROMAX_TEST_MODEL" "$WORK/fixtures/model.gguf" 2>/dev/null || cp "$CHROMAX_TEST_MODEL" "$WORK/fixtures/model.gguf"
fi
mkdir -p /mnt/qualification
mount -o loop "$WORK/rootfs.ext4" /mnt/qualification
trap 'umount /mnt/qualification' EXIT
mkdir -p /mnt/qualification/home/chromax/qualification
cp "$WORK/fixtures/"* /mnt/qualification/home/chromax/qualification/
chown -R 1000:1000 /mnt/qualification/home/chromax/qualification
sync
umount /mnt/qualification
trap - EXIT
if [ "${CHROMAX_PREPARE_ONLY:-0}" = 1 ]; then echo 'Prepared a disposable qualification root filesystem.'; exit 0; fi
MODEL_ARGS=()
if [ -n "${CHROMAX_TEST_MODEL:-}" ]; then MODEL_ARGS=(--model-sha256 "$(sha256sum "$CHROMAX_TEST_MODEL" | cut -d' ' -f1)"); fi
PYTHONPATH=/repo/src python3 /repo/scripts/qualify.py --architecture "$ARCH" --images "$IMAGES" \
    --rootfs "$WORK/rootfs.ext4" --evidence "$WORK/evidence-direct" --ssh-key "$WORK/id_ed25519" "${MODEL_ARGS[@]}"
