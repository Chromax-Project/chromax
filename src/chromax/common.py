"""Small, dependency-free primitives shared by the system tools."""
import contextlib
import fcntl
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time


class ChromaxError(Exception):
    pass


def atomic_write(path, data, mode=0o600):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".chromax-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            os.fchmod(stream.fileno(), mode)
            stream.write(data.encode() if isinstance(data, str) else data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def write_json(path, value, mode=0o600):
    atomic_write(path, json.dumps(value, indent=2, sort_keys=True) + "\n", mode)


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except FileNotFoundError:
        return default


@contextlib.contextmanager
def locked(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as stream:
        os.chmod(path, 0o600)
        fcntl.flock(stream, fcntl.LOCK_EX)
        yield


def run(argv, timeout=15, check=True):
    """Execute only a caller-constructed argument vector; never a shell."""
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout,
                                env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C"})
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ChromaxError(str(error)) from error
    if check and result.returncode:
        raise ChromaxError(result.stderr.strip()[:1000] or f"{argv[0]} exited {result.returncode}")
    return result.stdout.strip()


def require_root():
    if os.geteuid() != 0:
        raise ChromaxError("This change requires administrator access. Run with sudo.")


def audit(state, event, details):
    """Do not record prompts, credentials or model responses in the audit log."""
    path = Path(state) / "audit.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    with os.fdopen(fd, "a") as stream:
        stream.write(json.dumps({"time": int(time.time()), "event": event, **details}, sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
