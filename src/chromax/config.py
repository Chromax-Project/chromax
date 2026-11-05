import json
from pathlib import Path
from urllib.parse import urlparse
from .common import ChromaxError, atomic_write

DEFAULT = {
    "endpoint": "http://127.0.0.1:8081/v1", "model": "local",
    "api_key_file": "", "allow_remote": False,
    "timeout": 120, "max_tokens": 768,
}


def load(path="/etc/chromax/ai.json"):
    config = dict(DEFAULT)
    try:
        data = json.loads(Path(path).read_text())
        if not isinstance(data, dict) or set(data) - set(DEFAULT):
            raise ChromaxError("AI configuration contains unsupported fields")
        config.update(data)
    except FileNotFoundError:
        pass
    if not isinstance(config["endpoint"], str):
        raise ChromaxError("endpoint must be a URL")
    url = urlparse(config["endpoint"])
    if url.username or url.password or url.query or url.fragment or not url.hostname:
        raise ChromaxError("Endpoint URL must not contain credentials, queries or fragments")
    local = url.hostname in ("127.0.0.1", "::1", "localhost")
    if url.scheme not in ("http", "https") or (not local and (url.scheme != "https" or config["allow_remote"] is not True)):
        raise ChromaxError("Remote AI requires HTTPS and explicit allow_remote=true")
    for name, low, high in (("timeout", 1, 300), ("max_tokens", 1, 4096)):
        if type(config[name]) is not int or not low <= config[name] <= high:
            raise ChromaxError(f"Invalid {name}")
    if not isinstance(config["model"], str) or not config["model"] or len(config["model"]) > 200:
        raise ChromaxError("Invalid model name")
    if not isinstance(config["api_key_file"], str):
        raise ChromaxError("Invalid api_key_file")
    return config


def save(path, config):
    # Validate before replacing the live file.
    import tempfile
    with tempfile.TemporaryDirectory() as directory:
        candidate = Path(directory) / "config.json"
        candidate.write_text(json.dumps(config))
        validated = load(candidate)
    atomic_write(path, json.dumps(validated, indent=2) + "\n")
