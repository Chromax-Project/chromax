#!/usr/bin/env bash
set -euo pipefail
ARCH=${1:-aarch64}
IMAGES=${2:?Usage: run-vm.sh ARCH IMAGE_DIRECTORY}
case "$ARCH" in aarch64|x86_64) ;; *) exit 2;; esac
IMAGES=$(cd "$IMAGES" && pwd)
STATE=${CHROMAX_VM_STATE:-$PWD/.cache/vm-$ARCH}
mkdir -p "$STATE"
if ! command -v "qemu-system-$ARCH" >/dev/null || ! command -v qemu-img >/dev/null; then
    echo 'Install QEMU from your operating system package manager first.' >&2
    exit 1
fi
if [ ! -f "$STATE/root.qcow2" ]; then
    qemu-img create -f qcow2 -F raw -b "$IMAGES/rootfs.ext4" "$STATE/root.qcow2"
fi
if [ "$ARCH" = aarch64 ]; then
    exec qemu-system-aarch64 -machine virt -cpu cortex-a72 -m 2048 -smp 2 -nographic \
        -kernel "$IMAGES/Image" -append 'root=/dev/vda rw rootwait console=ttyAMA0' \
        -drive "file=$STATE/root.qcow2,if=none,id=root,format=qcow2" -device virtio-blk-device,drive=root \
        -netdev user,id=net0,hostfwd=tcp:127.0.0.1:2222-:22 -device virtio-net-device,netdev=net0
else
    exec qemu-system-x86_64 -machine q35 -cpu max -m 2048 -smp 2 -nographic \
        -kernel "$IMAGES/bzImage" -append 'root=/dev/vda rw rootwait console=ttyS0' \
        -drive "file=$STATE/root.qcow2,if=virtio,format=qcow2" \
        -netdev user,id=net0,hostfwd=tcp:127.0.0.1:2222-:22 -device virtio-net-pci,netdev=net0
fi
