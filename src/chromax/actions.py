"""Reviewable named actions. Generated prose is never an executable input."""
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import time
from .common import ChromaxError, atomic_write, write_json, read_json, locked, run, audit, require_root

SERVICES = {"network": "/etc/init.d/S40network", "ssh": "/etc/init.d/S50dropbear", "inference": "/etc/init.d/S70llama"}
ID = re.compile(r"^[0-9a-f]{24}$")


def validate(action, arguments):
    if not isinstance(arguments, dict):
        raise ChromaxError("Action arguments must be an object")
    if action == "hostname" and set(arguments) == {"name"}:
        name = arguments["name"]
        if isinstance(name, str) and re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?", name):
            return f"Set hostname to {name}"
    if action == "service-restart" and set(arguments) == {"service"} and arguments.get("service") in SERVICES:
        return f"Restart {arguments['service']}"
    raise ChromaxError("Unsupported action or arguments; supported actions: hostname, service-restart")


def create(state, action, arguments):
    require_root()
    summary = validate(action, arguments)
    plan_id = secrets.token_hex(12)
    plan = {"id": plan_id, "action": action, "arguments": arguments, "summary": summary,
            "created": int(time.time()), "expires": int(time.time()) + 900, "status": "pending"}
    write_json(Path(state) / "plans" / (plan_id + ".json"), plan)
    audit(state, "plan-created", {"id": plan_id, "action": action})
    return plan


def get(state, plan_id):
    if not isinstance(plan_id, str) or not ID.fullmatch(plan_id):
        raise ChromaxError("Invalid plan ID")
    plan = read_json(Path(state) / "plans" / (plan_id + ".json"))
    if plan is None:
        raise ChromaxError("Plan does not exist")
    validate(plan["action"], plan["arguments"])
    return plan


def apply(state, plan_id, confirmation, root="/"):
    require_root()
    with locked(Path(state) / "actions.lock"):
        plan = get(state, plan_id)
        if confirmation != plan_id:
            raise ChromaxError("Confirmation must match the complete plan ID")
        if plan["status"] != "pending" or plan["expires"] < time.time():
            raise ChromaxError("Plan is expired or already used")
        # Persist before executing: a crash must not permit replay of an action.
        plan["status"] = "applying"
        path = Path(state) / "plans" / (plan_id + ".json")
        write_json(path, plan)
        try:
            if plan["action"] == "hostname":
                name = plan["arguments"]["name"]
                hostname_path = Path(root) / "etc/hostname"
                previous = hostname_path.read_text() if hostname_path.exists() else ""
                plan["previous"] = previous
                write_json(path, plan)
                atomic_write(hostname_path, name + "\n", 0o644)
                if root == "/":
                    run(["/bin/hostname", name])
            else:
                if root != "/":
                    raise ChromaxError("Service actions are only available on the running system")
                run([SERVICES[plan["arguments"]["service"]], "restart"], timeout=60)
            plan["status"] = "applied"
            audit(state, "plan-applied", {"id": plan_id, "action": plan["action"]})
        except Exception:
            plan["status"] = "failed"
            audit(state, "plan-failed", {"id": plan_id, "action": plan["action"]})
            raise
        finally:
            write_json(path, plan)
        return plan
