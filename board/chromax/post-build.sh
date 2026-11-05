#!/bin/sh
set -eu
TARGET=$1
install -d "$TARGET/var/lib/chromax/models" "$TARGET/var/log/chromax" "$TARGET/etc/chromax" "$TARGET/home/chromax"
cat > "$TARGET/etc/os-release" <<'EOF'
NAME="Chromax Linux"
ID=chromax
PRETTY_NAME="Chromax Linux 0.1.0 (Prism)"
VERSION_ID=0.1.0
VERSION_CODENAME=prism
HOME_URL="https://github.com/Chromax-Project/chromax"
BUG_REPORT_URL="https://github.com/Chromax-Project/chromax/issues"
EOF
# Local console starts an unprivileged session. Password and SSH keys are
# provisioned explicitly; both accounts remain password-locked in images.
if grep -q '^BR2_aarch64=y' "$BR2_CONFIG"; then CONSOLE=ttyAMA0; else CONSOLE=ttyS0; fi
sed -i "s@^[^#].*getty.*$CONSOLE.*@$CONSOLE::respawn:/sbin/agetty -a chromax -L $CONSOLE 115200 vt100@" "$TARGET/etc/inittab"
cat >> "$TARGET/etc/sudoers" <<'EOF'

# The root entry point validates every argument. No arbitrary shell execution.
chromax ALL=(root) NOPASSWD: /usr/bin/chromaxctl
EOF
chmod 0440 "$TARGET/etc/sudoers"
cat > "$TARGET/etc/profile.d/chromax.sh" <<'EOF'
export PYTHONPATH=/usr/lib/chromax
if [ -t 1 ]; then
  printf '\n  Chromax · AI-native Linux\n  ai ask "what is running?"   |   chromaxctl help\n\n'
fi
EOF
printf 'DROPBEAR_ARGS="-s -w"\n' > "$TARGET/etc/default/dropbear"
printf 'kernel.dmesg_restrict=1\nkernel.kptr_restrict=2\nfs.protected_hardlinks=1\nfs.protected_symlinks=1\n' > "$TARGET/etc/sysctl.conf"
