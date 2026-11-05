import os
from pathlib import Path
import platform
import shutil
import time
from .common import run, ChromaxError


def status():
    memory = {}
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            key, value = line.split(":", 1)
            if key in ("MemTotal", "MemAvailable"):
                memory[key] = int(value.split()[0]) * 1024
    except (OSError, ValueError):
        pass
    disk = shutil.disk_usage("/")
    try:
        uptime = float(Path("/proc/uptime").read_text().split()[0])
    except (OSError, ValueError):
        uptime = None
    try:
        network = run(["/sbin/ip", "-j", "address", "show"], check=False)
        import json
        network = json.loads(network) if network else []
    except (ChromaxError, ValueError):
        network = []
    return {
        "hostname": platform.node(), "kernel": platform.release(),
        "architecture": platform.machine(), "cpus": os.cpu_count(),
        "load": list(os.getloadavg()), "memory": memory,
        "disk": {"total": disk.total, "used": disk.used, "free": disk.free},
        "uptime_seconds": uptime, "network": network, "time": int(time.time()),
    }


def doctor(state="/var/lib/chromax"):
    from .config import load
    checks = [{"name": "state directory", "ok": Path(state).is_dir()},
              {"name": "console service token", "ok": Path("/run/chromax/token").exists(), "detail": "Recover a stopped console with sudo chromaxctl recover"},
              {"name": "inference binary", "ok": shutil.which("llama-server") is not None},
              {"name": "TLS trust store", "ok": Path("/etc/ssl/certs/ca-certificates.crt").exists()}]
    try:
        cfg = load()
        checks.append({"name": "AI configuration", "ok": True, "endpoint": cfg["endpoint"]})
    except ChromaxError as error:
        checks.append({"name": "AI configuration", "ok": False, "error": str(error)})
    model = Path(state) / "models/current.gguf"
    checks.append({"name": "local model", "ok": model.exists(), "detail": "Provision with sudo chromaxctl model add FILE --sha256 HASH"})
    return checks
