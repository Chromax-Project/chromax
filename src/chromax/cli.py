import argparse
import getpass
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, ProxyHandler
from . import __version__, actions, config, models, packages, system
from .common import ChromaxError, atomic_write, require_root

STATE = "/var/lib/chromax"
APPS = "/opt/chromax/apps"


def api(path, body=None):
    try:
        token = Path("/run/chromax/token").read_text().strip()
        request = Request("http://127.0.0.1:8080" + path,
                          None if body is None else json.dumps(body).encode(),
                          {"Authorization": "Bearer " + token, "Content-Type": "application/json"})
        with build_opener(ProxyHandler({})).open(request, timeout=310) as response:
            return json.load(response)
    except HTTPError as error:
        try:
            message = json.load(error).get("error", "Request failed")
        except ValueError:
            message = "Request failed"
        raise ChromaxError(message) from error
    except (URLError, OSError) as error:
        raise ChromaxError("Chromax service is unavailable. Check /etc/init.d/S80chromax status.") from error


def safe_text(value):
    return "".join(c for c in value if c in "\n\t" or not unicodedata.category(c).startswith("C"))


def parser():
    p = argparse.ArgumentParser(prog="chromaxctl", description="Chromax Linux — your machine, understood")
    p.add_argument("--version", action="version", version=__version__)
    commands = p.add_subparsers(dest="command", required=True)
    for name in ("status", "doctor", "web-token", "chat", "serve", "help", "passwd"):
        commands.add_parser(name)
    ask = commands.add_parser("ask")
    ask.add_argument("question", nargs="+")
    plan = commands.add_parser("plan")
    action = plan.add_subparsers(dest="action", required=True)
    hostname = action.add_parser("hostname")
    hostname.add_argument("name")
    restart = action.add_parser("service-restart")
    restart.add_argument("service", choices=sorted(actions.SERVICES))
    show = commands.add_parser("show")
    show.add_argument("id")
    apply = commands.add_parser("apply")
    apply.add_argument("id")
    apply.add_argument("--confirm", required=True)
    model = commands.add_parser("model").add_subparsers(dest="model_command", required=True)
    model.add_parser("info")
    add = model.add_parser("add")
    add.add_argument("file")
    add.add_argument("--sha256", required=True)
    cfg = commands.add_parser("config")
    cfg.add_argument("--endpoint", required=True)
    cfg.add_argument("--model", default="local")
    cfg.add_argument("--allow-remote", action="store_true")
    cfg.add_argument("--api-key", action="store_true", help="Read an API key privately from the terminal")
    cfg.add_argument("--listen", choices=("127.0.0.1", "0.0.0.0"), default="127.0.0.1")
    key = commands.add_parser("ssh-key")
    key.add_argument("public_key", help="An authorized SSH public key for the chromax account")
    pkg = commands.add_parser("package").add_subparsers(dest="package_command", required=True)
    pkg.add_parser("list")
    build = pkg.add_parser("build")
    build.add_argument("source")
    build.add_argument("output")
    build.add_argument("--name", required=True)
    build.add_argument("--version", required=True)
    build.add_argument("--architecture", choices=("all", "aarch64", "x86_64"), required=True)
    build.add_argument("--entrypoint", required=True)
    install = pkg.add_parser("install")
    install.add_argument("bundle")
    install.add_argument("--signature", required=True)
    install.add_argument("--key", required=True)
    rollback = pkg.add_parser("rollback")
    rollback.add_argument("name")
    rollback.add_argument("version")
    run = pkg.add_parser("run")
    run.add_argument("name")
    run.add_argument("arguments", nargs=argparse.REMAINDER)
    trust = pkg.add_parser("trust")
    trust.add_argument("id")
    trust.add_argument("public_key")
    return p


def main(argv=None):
    p = parser()
    args = p.parse_args(argv)
    try:
        result = None
        if args.command == "help":
            p.print_help()
        elif args.command == "status":
            result = system.status()
        elif args.command == "doctor":
            result = system.doctor(STATE)
        elif args.command == "web-token":
            print(Path("/run/chromax/token").read_text().strip())
        elif args.command == "ask":
            print(safe_text(api("/v1/ask", {"question": " ".join(args.question)})["answer"]))
        elif args.command == "chat":
            print("Chromax assistant. Type /quit to leave. Each question receives a fresh system snapshot.")
            while True:
                try:
                    question = input("you › ").strip()
                except EOFError:
                    break
                if question == "/quit":
                    break
                if question:
                    try:
                        print(safe_text(api("/v1/ask", {"question": question})["answer"]))
                    except ChromaxError as error:
                        print(str(error), file=sys.stderr)
        elif args.command == "plan":
            arguments = {"name": args.name} if args.action == "hostname" else {"service": args.service}
            result = api("/v1/plans", {"action": args.action, "arguments": arguments})
            print(f"Review: {result['summary']}\nApply: sudo chromaxctl apply {result['id']} --confirm {result['id']}")
        elif args.command == "show":
            result = api("/v1/plans/" + args.id)
        elif args.command == "apply":
            result = actions.apply(STATE, args.id, args.confirm)
        elif args.command == "model":
            result = models.info(STATE) if args.model_command == "info" else models.add(STATE, args.file, args.sha256)
        elif args.command == "config":
            require_root()
            key_path = "/etc/chromax/credentials/api.key" if args.api_key else ""
            if args.api_key:
                key = getpass.getpass("API key: ").strip()
                if not key or len(key) > 4096 or "\n" in key or "\r" in key:
                    raise ChromaxError("Invalid API key")
                atomic_write(key_path, key + "\n")
            config.save("/etc/chromax/ai.json", {"endpoint": args.endpoint, "model": args.model,
                        "allow_remote": args.allow_remote, "api_key_file": key_path})
            atomic_write("/etc/chromax/listen", args.listen + "\n", 0o644)
            result = {"configured": True, "restart_required": "sudo chromaxctl plan service-restart inference (when model changes); restart S80chromax when listener changes"}
        elif args.command == "ssh-key":
            require_root()
            import base64
            key = args.public_key.strip()
            fields = key.split()
            if len(fields) < 2 or fields[0] not in ("ssh-ed25519", "ssh-rsa", "ecdsa-sha2-nistp256") or "\n" in key:
                raise ChromaxError("Provide a single SSH public key without options")
            try:
                decoded = base64.b64decode(fields[1], validate=True)
            except ValueError as error:
                raise ChromaxError("Invalid SSH key encoding") from error
            kind_len = int.from_bytes(decoded[:4], "big")
            if decoded[4:4 + kind_len] != fields[0].encode() or len(decoded) < 32:
                raise ChromaxError("Invalid SSH public key")
            import pwd
            account = pwd.getpwnam("chromax")
            directory = Path("/home/chromax/.ssh")
            directory.mkdir(mode=0o700, exist_ok=True)
            directory.chmod(0o700)
            atomic_write(directory / "authorized_keys", key + "\n")
            os.chown(directory, account.pw_uid, account.pw_gid)
            os.chown(directory / "authorized_keys", account.pw_uid, account.pw_gid)
            result = {"configured": True, "user": "chromax"}
        elif args.command == "passwd":
            require_root()
            password = getpass.getpass("New password for chromax: ")
            if len(password) < 12 or "\n" in password or ":" in password:
                raise ChromaxError("Use at least 12 characters, without newlines or colons")
            if password != getpass.getpass("Repeat password: "):
                raise ChromaxError("Passwords do not match")
            process = subprocess.run(["/usr/sbin/chpasswd"], input="chromax:" + password + "\n", text=True, capture_output=True)
            if process.returncode:
                raise ChromaxError("Password update failed")
            result = {"password_updated": True, "user": "chromax"}
        elif args.command == "serve":
            from .server import serve
            serve()
        elif args.command == "package":
            op = args.package_command
            if op == "list":
                result = packages.list_installed(APPS)
            elif op == "build":
                if os.geteuid() == 0 and os.environ.get("SUDO_USER"):
                    raise ChromaxError("Build packages as the unprivileged user")
                result = packages.build(args.source, args.output, args.name, args.version, args.architecture, args.entrypoint)
            elif op == "install":
                result = packages.install(STATE, APPS, args.bundle, args.signature, args.key)
            elif op == "rollback":
                result = packages.rollback(STATE, APPS, args.name, args.version)
            elif op == "run":
                # A sudo invocation must never turn a bundle into an arbitrary root command.
                if os.geteuid() == 0:
                    raise ChromaxError("Run application bundles as an unprivileged user")
                command = packages.command(APPS, args.name, args.arguments)
                os.execv(command[0], command)
            elif op == "trust":
                require_root()
                if not packages.NAME.fullmatch(args.id):
                    raise ChromaxError("Invalid key ID")
                from .common import run
                content = Path(args.public_key).read_bytes()
                if len(content) > 16384 or not content.startswith(b"-----BEGIN PUBLIC KEY-----"):
                    raise ChromaxError("Expected a PEM public key")
                import tempfile
                with tempfile.TemporaryDirectory() as directory:
                    candidate = Path(directory) / "key.pem"
                    candidate.write_bytes(content)
                    text = run(["/usr/bin/openssl", "pkey", "-pubin", "-in", str(candidate), "-text", "-noout"])
                    if "ED25519" not in text:
                        raise ChromaxError("Only Ed25519 signing keys are supported")
                atomic_write(Path("/etc/chromax/keys") / (args.id + ".pem"), content, 0o644)
                result = {"trusted_key": args.id}
        if result is not None:
            print(json.dumps(result, indent=2))
        return 0
    except (ChromaxError, OSError, ValueError, KeyError) as error:
        print("chromax: " + safe_text(str(error)), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
