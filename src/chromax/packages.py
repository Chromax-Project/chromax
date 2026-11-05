"""Signed, versioned application bundles without maintainer scripts.

The base OS is rebuilt as an image. Extensions live under /opt/chromax/apps;
only an atomic 'current' symlink changes on activation or rollback.
"""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import tarfile
import tempfile
from .common import ChromaxError, atomic_write, audit, locked, read_json, write_json, run, require_root

NAME = re.compile(r"^[a-z][a-z0-9-]{0,47}$")
VERSION = re.compile(r"^[0-9][a-zA-Z0-9.+_-]{0,63}$")
MAX_BYTES = 1024**3


def validate_manifest(manifest):
    if not isinstance(manifest, dict) or set(manifest) != {"format", "name", "version", "architecture", "entrypoint", "files"}:
        raise ChromaxError("Invalid bundle manifest fields")
    if manifest["format"] != 1 or not NAME.fullmatch(str(manifest["name"])) or not VERSION.fullmatch(str(manifest["version"])):
        raise ChromaxError("Invalid package name, version or format")
    if manifest["architecture"] not in ("aarch64", "x86_64", "all"):
        raise ChromaxError("Invalid package architecture")
    files = manifest["files"]
    if not isinstance(files, dict) or not 1 <= len(files) <= 10000:
        raise ChromaxError("Bundle must contain 1–10000 files")
    for name, entry in files.items():
        path = PurePosixPath(name)
        if not name or path.is_absolute() or ".." in path.parts or str(path) != name or "\\" in name or len(name) > 240:
            raise ChromaxError("Unsafe package path")
        if not isinstance(entry, dict) or set(entry) != {"sha256", "mode"}:
            raise ChromaxError("Invalid file metadata")
        if not re.fullmatch(r"[0-9a-f]{64}", str(entry["sha256"])) or entry["mode"] not in (0o644, 0o755):
            raise ChromaxError("Only regular files with mode 0644 or 0755 are allowed")
    if manifest["entrypoint"] not in files or files[manifest["entrypoint"]]["mode"] != 0o755:
        raise ChromaxError("Entrypoint must be an executable member")
    return manifest


def build(source, output, name, version, architecture, entrypoint):
    source = Path(source).resolve()
    files = {}
    for path in sorted(source.rglob("*")):
        if path.is_symlink():
            raise ChromaxError("Source bundles must not contain symlinks")
        if path.is_file():
            files[path.relative_to(source).as_posix()] = {
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "mode": 0o755 if path.stat().st_mode & 0o111 else 0o644,
            }
    manifest = validate_manifest({"format": 1, "name": name, "version": version,
                                 "architecture": architecture, "entrypoint": entrypoint, "files": files})
    import io
    with tarfile.open(output, "w:gz", format=tarfile.USTAR_FORMAT) as bundle:
        data = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
        item = tarfile.TarInfo("manifest.json")
        item.size, item.mode, item.mtime = len(data), 0o644, 0
        bundle.addfile(item, io.BytesIO(data))
        for name, entry in files.items():
            item = tarfile.TarInfo("payload/" + name)
            item.mode, item.mtime = entry["mode"], 0
            item.size = (source / name).stat().st_size
            with (source / name).open("rb") as stream:
                bundle.addfile(item, stream)
    return manifest


def verify_signature(bundle, signature, key):
    # The trust key is selected from the root-managed trust directory by key ID,
    # never supplied as an arbitrary key alongside the untrusted bundle.
    run(["/usr/bin/openssl", "pkeyutl", "-verify", "-pubin", "-inkey", str(key),
         "-rawin", "-in", str(bundle), "-sigfile", str(signature)], timeout=60)


def install(state, apps, bundle, signature, key_id, trust="/etc/chromax/keys"):
    require_root()
    if not NAME.fullmatch(key_id):
        raise ChromaxError("Invalid signing key ID")
    key = Path(trust) / (key_id + ".pem")
    if not key.is_file():
        raise ChromaxError("Signing key is not trusted")
    with locked(Path(state) / "packages.lock"):
        # Freeze the bytes before verification so the caller cannot replace the
        # archive between signature validation and extraction.
        staging_root = Path(apps) / ".staging"
        staging_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if Path(bundle).stat().st_size > MAX_BYTES or Path(signature).stat().st_size > 4096:
            raise ChromaxError("Bundle or signature exceeds the size limit")
        with tempfile.TemporaryDirectory(dir=staging_root) as tmp:
            tmp = Path(tmp)
            archive = tmp / "bundle.cxpk"
            with open(bundle, "rb") as src, archive.open("wb") as dest:
                copied = 0
                while chunk := src.read(1024 * 1024):
                    copied += len(chunk)
                    if copied > MAX_BYTES:
                        raise ChromaxError("Bundle exceeds 1 GiB")
                    dest.write(chunk)
            if archive.stat().st_size > MAX_BYTES:
                raise ChromaxError("Bundle exceeds 1 GiB")
            frozen_signature = tmp / "bundle.sig"
            with open(signature, "rb") as stream:
                signature_bytes = stream.read(4097)
            if len(signature_bytes) != 64:
                raise ChromaxError("Ed25519 signatures must contain exactly 64 bytes")
            atomic_write(frozen_signature, signature_bytes)
            verify_signature(archive, frozen_signature, key)
            with tarfile.open(archive, "r:gz") as tar:
                members, names, total = [], set(), 0
                for member in tar:
                    total += member.size
                    if len(members) >= 10001 or member.name in names:
                        raise ChromaxError("Duplicate members or too many files")
                    if not member.isfile() or member.size < 0 or total > MAX_BYTES:
                        raise ChromaxError("Bundle contains special files or exceeds 1 GiB unpacked")
                    members.append(member)
                    names.add(member.name)
                by_name = {m.name: m for m in members}
                if "manifest.json" not in by_name or by_name["manifest.json"].size > 4 * 1024**2:
                    raise ChromaxError("Missing or oversized manifest")
                manifest = validate_manifest(json.load(tar.extractfile(by_name["manifest.json"])))
                if manifest["architecture"] not in ("all", platform.machine()):
                    raise ChromaxError("Package architecture does not match this machine")
                if set(by_name) != {"manifest.json"} | {"payload/" + p for p in manifest["files"]}:
                    raise ChromaxError("Archive members differ from signed manifest")
                payload = tmp / "payload"
                payload.mkdir()
                for name, entry in manifest["files"].items():
                    member = by_name["payload/" + name]
                    target = payload / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    digest = hashlib.sha256()
                    with tar.extractfile(member) as src, target.open("xb") as dest:
                        while chunk := src.read(1024 * 1024):
                            digest.update(chunk)
                            dest.write(chunk)
                        dest.flush()
                        os.fsync(dest.fileno())
                    if digest.hexdigest() != entry["sha256"]:
                        raise ChromaxError(f"Payload checksum mismatch: {name}")
                    target.chmod(entry["mode"])
            package_root = Path(apps) / manifest["name"]
            package_root.mkdir(parents=True, exist_ok=True)
            final = package_root / manifest["version"]
            if final.exists():
                raise ChromaxError("This version is already installed; use rollback to select it")
            write_json(payload / ".chromax-manifest.json", manifest, 0o644)
            os.rename(payload, final)
            _activate(package_root, manifest["version"])
            audit(state, "package-installed", {"name": manifest["name"], "version": manifest["version"], "key": key_id})
            return manifest


def _activate(root, version):
    temporary = root / ".current-new"
    temporary.unlink(missing_ok=True)
    temporary.symlink_to(version)
    os.replace(temporary, root / "current")
    fd = os.open(root, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def rollback(state, apps, name, version):
    require_root()
    if not NAME.fullmatch(name) or not VERSION.fullmatch(version):
        raise ChromaxError("Invalid package name or version")
    with locked(Path(state) / "packages.lock"):
        root = Path(apps) / name
        manifest = read_json(root / version / ".chromax-manifest.json")
        if manifest is None:
            raise ChromaxError("Requested version is not installed")
        validate_manifest(manifest)
        _activate(root, version)
        audit(state, "package-rollback", {"name": name, "version": version})
        return manifest


def list_installed(apps):
    result = []
    for path in sorted(Path(apps).glob("*/current/.chromax-manifest.json")):
        result.append(read_json(path))
    return result


def command(apps, name, arguments):
    if not NAME.fullmatch(name):
        raise ChromaxError("Invalid package name")
    root = Path(apps) / name / "current"
    manifest = read_json(root / ".chromax-manifest.json")
    if manifest is None:
        raise ChromaxError("Package is not installed")
    validate_manifest(manifest)
    return [str(root / manifest["entrypoint"]), *arguments]
