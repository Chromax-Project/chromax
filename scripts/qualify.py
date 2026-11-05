#!/usr/bin/env python3
"""Exercise actual source-built guests; never substitute host tests for boot proof."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import subprocess
import sys
import threading
import time


class Guest:
    def __init__(self, command, log):
        self.log = Path(log).open("wb")
        self.data = bytearray()
        self.condition = threading.Condition()
        self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        self.thread = threading.Thread(target=self.read, daemon=True)
        self.thread.start()

    def read(self):
        while chunk := os.read(self.process.stdout.fileno(), 4096):
            self.log.write(chunk)
            self.log.flush()
            with self.condition:
                self.data.extend(chunk)
                self.condition.notify_all()
        with self.condition:
            self.condition.notify_all()

    def wait(self, pattern, timeout=180, offset=0):
        deadline = time.monotonic() + timeout
        pattern = re.compile(pattern, re.DOTALL)
        with self.condition:
            while True:
                data = bytes(self.data[offset:])
                match = pattern.search(data)
                if match:
                    return data, match
                if self.process.poll() is not None:
                    raise RuntimeError("Guest exited before expected output: " + data[-3000:].decode(errors="replace"))
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("Guest output timeout: " + data[-3000:].decode(errors="replace"))
                self.condition.wait(min(remaining, 1))

    def command(self, command, timeout=120):
        marker = "__CHROMAX_" + secrets.token_hex(8)
        offset = len(self.data)
        line = command + "; _cx=$?; printf '\\n" + marker + "_%s\\n' \"$_cx\"\n"
        self.process.stdin.write(line.encode())
        self.process.stdin.flush()
        data, match = self.wait(marker.encode() + rb"_(\d+)\r?\n", timeout, offset)
        output = data[:match.start()].decode(errors="replace")
        if match.group(1) != b"0":
            raise RuntimeError("Guest command failed: " + output[-5000:])
        return output

    def shutdown(self):
        if self.process.poll() is None:
            self.process.stdin.write(b"sudo -n chromaxctl poweroff\n")
            self.process.stdin.flush()
            try:
                self.process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                self.process.wait(timeout=10)
        self.thread.join(timeout=2)
        self.log.close()


def qemu_command(arch, images, rootfs, firmware=False, accelerator="tcg", firmware_path=None):
    common = ["-m", "2048", "-smp", "2", "-nographic", "-no-reboot",
              "-netdev", "user,id=net0,hostfwd=tcp:127.0.0.1:22222-:22"]
    if arch == "aarch64":
        command = ["qemu-system-aarch64", "-machine", "virt", "-cpu", "cortex-a72", *common,
                   "-device", "virtio-net-device,netdev=net0", "-drive", f"file={rootfs},if=none,id=root,format=raw",
                   "-device", "virtio-blk-device,drive=root"]
        if accelerator != "tcg":
            command[command.index("cortex-a72")] = "host"
            command += ["-accel", accelerator]
        if firmware:
            command += ["-bios", str(firmware_path or "/usr/share/qemu-efi-aarch64/QEMU_EFI.fd")]
        else:
            command += ["-kernel", str(images / "Image"), "-append", "console=ttyAMA0 root=/dev/vda rw rootwait"]
    else:
        command = ["qemu-system-x86_64", "-machine", "q35", "-cpu", "max", *common,
                   "-device", "virtio-net-pci,netdev=net0", "-drive", f"file={rootfs},if=virtio,format=raw"]
        if firmware:
            command += ["-bios", str(firmware_path or "/usr/share/OVMF/OVMF_CODE_4M.fd")]
        else:
            command += ["-kernel", str(images / "bzImage"), "-append", "console=ttyS0 root=/dev/vda rw rootwait"]
    return command


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--architecture", choices=("aarch64", "x86_64"), required=True)
    parser.add_argument("--images", type=Path, required=True)
    parser.add_argument("--rootfs", type=Path, required=True, help="Disposable writable working copy, never a release master")
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--model-sha256")
    parser.add_argument("--ssh-key", type=Path)
    parser.add_argument("--uefi", action="store_true")
    parser.add_argument("--accelerator", choices=("tcg", "hvf", "kvm"), default="tcg")
    parser.add_argument("--firmware-path", type=Path)
    args = parser.parse_args()
    if args.rootfs.resolve() in ((args.images / "rootfs.ext4").resolve(), (args.images / "chromax.img").resolve()):
        parser.error("Qualification requires a disposable working copy, never a release master")
    args.evidence.mkdir(parents=True, exist_ok=True)
    results = {"architecture": args.architecture, "accelerator": args.accelerator, "firmware": "UEFI" if args.uefi else "direct", "checks": [], "started": int(time.time())}
    guest = None
    def record(name, output=None):
        results["checks"].append({"name": name, "passed": True, **({"output": output} if output is not None else {})})
        print("PASS " + name, flush=True)
    try:
        command = qemu_command(args.architecture, args.images, args.rootfs, args.uefi, args.accelerator, args.firmware_path)
        guest = Guest(command, args.evidence / "boot-1.log")
        guest.wait(rb"\r?\n\$ ", timeout=240)
        guest.command("test \"$(id -u)\" = 1000 && test \"$(uname -r)\" = 6.18.60", timeout=30)
        record("boot and unprivileged session")
        output = guest.command("chromaxctl status && chromaxctl doctor")
        record("native management tools", output[-5000:])
        guest.command("curl --fail --max-time 30 -o /tmp/chromax-tls https://www.kernel.org && test -s /tmp/chromax-tls", timeout=45)
        record("DHCP DNS and verified HTTPS")
        guest.command("python3 -c 'import urllib.request,urllib.error; r=urllib.request.urlopen(\"http://127.0.0.1:8080/healthz\"); assert r.status==200'")
        guest.command("python3 -c 'import pathlib,urllib.request,json; t=pathlib.Path(\"/run/chromax/token\").read_text().strip(); q=urllib.request.Request(\"http://127.0.0.1:8080/v1/status\",headers={\"Authorization\":\"Bearer \"+t}); assert json.load(urllib.request.urlopen(q))[\"kernel\"]==\"6.18.60\"'")
        record("authenticated guest HTTP API")
        guest.command("python3 -c 'import pathlib,urllib.request,json; t=pathlib.Path(\"/run/chromax/token\").read_text().strip(); q=urllib.request.Request(\"http://127.0.0.1:8080/v1/doctor\",headers={\"Authorization\":\"Bearer \"+t}); assert any(c[\"name\"]==\"root password locked\" and c[\"ok\"] for c in json.load(urllib.request.urlopen(q)))'")
        record("distributable image has no root password")
        output = guest.command("chromaxctl plan hostname chromax-qualified")
        plan = re.search(r'"id": "([a-f0-9]{24})"', output).group(1)
        guest.command(f"sudo -n chromaxctl apply {plan} --confirm {plan} && test \"$(hostname)\" = chromax-qualified")
        guest.command(f"if sudo -n chromaxctl apply {plan} --confirm {plan}; then false; else true; fi")
        record("review apply and replay rejection")
        if args.ssh_key:
            guest.command("sudo -n chromaxctl ssh-key \"$(cat /home/chromax/qualification/id_ed25519.pub)\"")
            ssh = ["ssh", "-i", str(args.ssh_key), "-p", "22222", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new",
                   "-o", f"UserKnownHostsFile={args.evidence / 'known_hosts'}", "-o", "ConnectTimeout=20"]
            out = subprocess.check_output([*ssh, "chromax@127.0.0.1", "id -u"], stderr=subprocess.STDOUT, timeout=30)
            if not out.decode().strip().endswith("1000"):
                raise RuntimeError("SSH did not use the unprivileged account")
            if subprocess.run([*ssh, "root@127.0.0.1", "true"], capture_output=True, timeout=30).returncode == 0:
                raise RuntimeError("Root SSH unexpectedly succeeded")
            record("SSH public key login and root rejection")
        fixture = "/home/chromax/qualification"
        guest.command(f"sudo -n chromaxctl package trust qualification {fixture}/publisher-public.pem")
        for version in ("1.0.0", "2.0.0"):
            guest.command(f"sudo -n chromaxctl package install {fixture}/hello-{version}.cxpk --signature {fixture}/hello-{version}.cxpk.sig --key qualification")
            output = guest.command("chromaxctl package run hello")
            if "hello-" + version not in output:
                raise RuntimeError("Wrong package version executed")
        guest.command("sudo -n chromaxctl package rollback hello 1.0.0")
        if "hello-1.0.0" not in guest.command("chromaxctl package run hello"):
            raise RuntimeError("Rollback did not activate prior version")
        record("guest Ed25519 install upgrade execution and rollback")
        if args.model_sha256:
            guest.command("sudo -n chromaxctl config --endpoint http://127.0.0.1:8081/v1 --model local --max-tokens 64 --timeout 300")
            guest.command(f"sudo -n chromaxctl model add {fixture}/model.gguf --sha256 {shlex.quote(args.model_sha256)}", timeout=60)
            output = guest.command("chromaxctl plan service-restart inference")
            plan = re.search(r'"id": "([a-f0-9]{24})"', output).group(1)
            guest.command(f"sudo -n chromaxctl apply {plan} --confirm {plan}")
            guest.command("for i in $(seq 1 120); do curl -fsS http://127.0.0.1:8081/health >/tmp/inference-health && break; sleep 1; done; grep -q ok /tmp/inference-health", timeout=150)
            # Bound integration generation while still executing the actual model.
            output = guest.command("python3 -c 'import urllib.request,json; b=json.dumps({\"messages\":[{\"role\":\"user\",\"content\":\"Say hello in one short sentence.\"}],\"max_tokens\":24,\"chat_template_kwargs\":{\"enable_thinking\":False},\"temperature\":0,\"stream\":False}).encode(); r=urllib.request.Request(\"http://127.0.0.1:8081/v1/chat/completions\",b,{\"Content-Type\":\"application/json\"}); d=json.load(urllib.request.urlopen(r,timeout=120)); a=d[\"choices\"][0][\"message\"][\"content\"]; assert a.strip(); print(\"ACTUAL_MODEL_RESPONSE=\"+a)'", timeout=140)
            record("actual local GGUF inference", output[-2500:])
            output = guest.command("ai ask 'Say hello briefly.'", timeout=320)
            record("integrated assistant with actual local model", output[-2500:])
            output = guest.command("ai propose 'Set the hostname to prism-test'", timeout=320)
            if 'Set hostname to prism-test' not in output:
                raise RuntimeError("The local model did not translate the hostname intent correctly")
            record("actual model translates natural-language intent into a pending plan", output[-2000:])
        guest.command("printf 'persistent-state\\n' > /home/chromax/persistence-proof && sync")
        guest.shutdown()
        guest = Guest(command, args.evidence / "boot-2.log")
        guest.wait(rb"\r?\n\$ ", timeout=240)
        guest.command("test \"$(hostname)\" = chromax-qualified && grep -q persistent-state /home/chromax/persistence-proof && chromaxctl package run hello")
        record("hostname user data and app selection persist across reboot")
        if args.model_sha256:
            guest.command("test -f /var/lib/chromax/models/current.gguf && for i in $(seq 1 120); do curl -fsS http://127.0.0.1:8081/health >/tmp/inference-health && break; sleep 1; done; grep -q ok /tmp/inference-health", timeout=150)
            record("model persists and inference starts automatically after reboot")
        results["passed"] = True
    except Exception as error:
        results["passed"] = False
        results["error"] = str(error)
        print("FAIL " + str(error), flush=True)
    finally:
        if guest:
            guest.shutdown()
        results["finished"] = int(time.time())
        (args.evidence / "qualification.json").write_text(json.dumps(results, indent=2) + "\n")
    return 0 if results["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
