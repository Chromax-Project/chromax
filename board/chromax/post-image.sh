#!/bin/sh
set -eu
BOARD=$BR2_EXTERNAL_CHROMAX_PATH/board/chromax
if grep -q '^BR2_aarch64=y' "$BR2_CONFIG"; then
    KERNEL=Image
    CONSOLE=ttyAMA0
else
    KERNEL=bzImage
    CONSOLE=ttyS0
fi
UUID=$("$HOST_DIR/sbin/dumpe2fs" "$BINARIES_DIR/rootfs.ext4" 2>/dev/null | sed -n 's/^Filesystem UUID: *//p')
test -n "$UUID"
cp "$BINARIES_DIR/$KERNEL" "$BINARIES_DIR/efi-part/kernel"
cat > "$BINARIES_DIR/efi-part/EFI/BOOT/grub.cfg" <<EOF
set default=0
set timeout=3
menuentry "Chromax Linux · Prism" {
    linux /kernel root=PARTUUID=$UUID rootwait rw console=$CONSOLE,115200 console=tty0
}
EOF
sed "s/ROOT_UUID/$UUID/g" "$BOARD/genimage.cfg" > "$BINARIES_DIR/genimage.cfg"
support/scripts/genimage.sh -c "$BINARIES_DIR/genimage.cfg"
