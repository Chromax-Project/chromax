"""Whole-disk image installer. Never selects or partitions a device implicitly."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import struct
import sys
from .common import ChromaxError, require_root, run


def find_device(nodes, target):
    for node in nodes:
        if node.get("name") == target:
            return node
        found = find_device(node.get("children", []), target)
        if found:
            return found
    return None


def validate_target(node, image_size):
    if not node or node.get("type") not in ("disk", "loop"):
        raise ChromaxError("Target must be a whole disk, never a partition")
    if node.get("ro"):
        raise ChromaxError("Target is read-only")
    if int(node.get("size", 0)) < image_size:
        raise ChromaxError("Target is smaller than the image")
    def busy(item):
        return any(item.get("mountpoints") or []) or any(busy(c) for c in item.get("children", []))
    if busy(node):
        raise ChromaxError("Target or one of its partitions is mounted or used as swap")


def digest_file(stream):
    digest = hashlib.sha256()
    stream.seek(0)
    while chunk := stream.read(4 * 1024 * 1024):
        digest.update(chunk)
    stream.seek(0)
    return digest.hexdigest()


def inspect(device, image_size):
    listing = json.loads(run(["/usr/bin/lsblk", "--json", "--bytes", "--paths", "--output", "NAME,TYPE,SIZE,MOUNTPOINTS,RO"]))
    node = find_device(listing.get("blockdevices", []), device)
    validate_target(node, image_size)
    return node


def main(argv=None):
    parser = argparse.ArgumentParser(description="Install a verified Chromax image onto an explicitly selected disposable whole disk")
    parser.add_argument("image")
    parser.add_argument("device")
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--confirm", help="Exact resolved device path; omitting it performs a dry run")
    args = parser.parse_args(argv)
    try:
        if not re.fullmatch(r"[0-9a-f]{64}", args.sha256):
            raise ChromaxError("Supply the image's published SHA-256 checksum")
        image = Path(args.image).resolve(strict=True)
        device = str(Path(args.device).resolve(strict=True))
        if not device.startswith("/dev/") or not stat.S_ISBLK(os.stat(device).st_mode):
            raise ChromaxError("Target must be a Linux block device under /dev")
        with image.open("rb") as source:
            image_stat = os.fstat(source.fileno())
            if not stat.S_ISREG(image_stat.st_mode):
                raise ChromaxError("Image must be a regular file")
            if digest_file(source) != args.sha256:
                raise ChromaxError("Image checksum mismatch")
            # Require a GPT disk image, not an arbitrary kernel or rootfs blob.
            source.seek(512)
            if source.read(8) != b"EFI PART":
                raise ChromaxError("Image does not contain a GPT partition table")
            source.seek(0)
            node = inspect(device, image_stat.st_size)
            review = {"target": device, "target_bytes": int(node["size"]), "image_bytes": image_stat.st_size,
                      "sha256": args.sha256, "effect": "Erase target disk contents and install Chromax"}
            print(json.dumps(review, indent=2))
            if args.confirm is None:
                print("Dry run. No data was written. To install, repeat with --confirm " + device)
                return 0
            if args.confirm != device:
                raise ChromaxError("Confirmation must exactly match the resolved whole-disk device path")
            require_root()
            # O_EXCL on a block device fails if a filesystem currently holds it.
            fd = os.open(device, os.O_RDWR | os.O_EXCL)
            try:
                inspect(device, image_stat.st_size)
                actual_size = struct.unpack("Q", fcntl.ioctl(fd, 0x80081272, b"\0" * 8))[0]  # BLKGETSIZE64
                if actual_size < image_stat.st_size:
                    raise ChromaxError("Target size changed; refusing to write")
                with os.fdopen(os.dup(fd), "r+b", buffering=0) as target:
                    written_digest = hashlib.sha256()
                    while chunk := source.read(4 * 1024 * 1024):
                        written_digest.update(chunk)
                        view = memoryview(chunk)
                        while view:
                            count = target.write(view)
                            if count is None or count <= 0:
                                raise ChromaxError("Short write to target disk")
                            view = view[count:]
                    os.fsync(fd)
                    if written_digest.hexdigest() != args.sha256:
                        raise ChromaxError("Source image changed during installation; target must be reinstalled")
                    target.seek(0)
                    readback = hashlib.sha256()
                    remaining = image_stat.st_size
                    while remaining:
                        chunk = target.read(min(4 * 1024 * 1024, remaining))
                        if not chunk:
                            raise ChromaxError("Target verification ended early")
                        readback.update(chunk)
                        remaining -= len(chunk)
                    if readback.hexdigest() != args.sha256:
                        raise ChromaxError("Target readback checksum mismatch")
                try:
                    fcntl.ioctl(fd, 0x125F)  # BLKRRPART
                except OSError:
                    print("Partition table reread deferred; unplug/replug the disk before use.")
            finally:
                os.close(fd)
            print("Installed and verified. Boot the target with UEFI firmware.")
            print("If the target is larger, relocate the backup GPT header with sgdisk -e before growing the root partition.")
            return 0
    except (ChromaxError, OSError, ValueError) as error:
        print("chromax-install: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
