"""Explicit, checksummed model provisioning; no unsolicited downloads."""
import hashlib
import os
from pathlib import Path
import re
import shutil
import tempfile
from .common import ChromaxError, atomic_write, audit, locked, read_json, write_json, require_root


def add(state, source, expected):
    require_root()
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise ChromaxError("A lowercase SHA-256 checksum is required")
    source = Path(source)
    if not source.is_file() or source.stat().st_size > 32 * 1024**3:
        raise ChromaxError("Model must be a regular GGUF file no larger than 32 GiB")
    directory = Path(state) / "models"
    directory.mkdir(parents=True, exist_ok=True)
    with locked(Path(state) / "models.lock"):
        fd, tmp = tempfile.mkstemp(prefix=".model-", dir=directory)
        try:
            digest = hashlib.sha256()
            size = 0
            with source.open("rb") as src, os.fdopen(fd, "wb") as dest:
                header = src.read(8)
                if header[:4] != b"GGUF" or int.from_bytes(header[4:8], "little") not in (2, 3):
                    raise ChromaxError("File does not have a supported GGUF v2/v3 header")
                src.seek(0)
                while chunk := src.read(1024 * 1024):
                    size += len(chunk)
                    if size > 32 * 1024**3:
                        raise ChromaxError("Model exceeds 32 GiB")
                    digest.update(chunk)
                    dest.write(chunk)
                dest.flush()
                os.fsync(dest.fileno())
                os.fchmod(dest.fileno(), 0o644)
            if digest.hexdigest() != expected:
                raise ChromaxError("Model checksum mismatch; existing model is unchanged")
            final = directory / (expected + ".gguf")
            os.replace(tmp, final)
            link = directory / ".current-new"
            link.unlink(missing_ok=True)
            link.symlink_to(final.name)
            os.replace(link, directory / "current.gguf")
            metadata = {"sha256": expected, "bytes": size, "format": "GGUF", "filename": source.name}
            write_json(directory / "current.json", metadata, 0o644)
            audit(state, "model-added", {"sha256": expected, "bytes": size})
            return metadata
        finally:
            Path(tmp).unlink(missing_ok=True)


def info(state):
    return read_json(Path(state) / "models/current.json", {"configured": False})
