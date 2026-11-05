# Architecture: Prism

Decision date: 2026-11-05. The initial supported product is a headless Linux
workstation/server and VM distribution with a browser system interface.

## Independent source-built base

Chromax starts with the upstream kernel and composes its own root filesystem.
Buildroot is the build system, not a parent binary distribution. Its external-tree
interface keeps Chromax configuration, packages, policy and UI in this repository.
Toolchain, libc, init, utilities, Python and llama.cpp are built from source.
The Ubuntu container supplies build tools only; none of its rootfs is copied into
the target. ARM64 and x86-64 use a common userspace and architecture-specific
kernel and EFI loader configurations.

The initial boot model is UEFI → GRUB → Linux → BusyBox init → network and SSH →
unprivileged inference → Chromax console. Kernel direct boot is also supported for
VM diagnostics. The filesystem is ext4 and writable, and survives normal reboots.
The flashable disk is GPT with a FAT EFI partition and an ext4 root partition.
Kernel root discovery uses a partition UUID rather than assuming SATA/NVMe/virtio
device names.

## AI is an interface, not an authority

The assistant gets a bounded, structured snapshot: hostname, kernel, architecture,
CPU count/load, memory, root filesystem usage, uptime and network addresses. It
does not receive shell history, arbitrary file content, credentials or logs.
Queries are single-turn so hidden conversation history cannot accumulate
privileged context. Local CPU inference is the default. Remote inference is
explicitly configured, requires HTTPS, and sends this snapshot and the user's
question to the configured provider. No telemetry or model download runs at boot.

The inference process runs as `chromax-ai`; it cannot access the console bearer
token or root-owned pending plans. The console daemon is a small privileged
broker. Its HTTP API permits observation, chat and plan creation, but has no
apply endpoint. It uses neither `shell=True` nor evaluation of generated code.

Supported plans are typed, allowlisted operations: hostname changes and restart
of networking, SSH, inference or the console. `ai propose` requests schema-constrained
JSON from the model, then revalidates it against the same deterministic policy
before creating a pending plan. Invalid or unsupported responses create no plan.
Chat itself remains read-only. Plan IDs are cryptographically random. Plan
creation records a validated action, summary, expiry and pending state. Applying
requires the full ID twice through the root CLI. A lock serializes applies; the
plan is marked applying before execution so a crash cannot silently replay it.
Audit entries identify actions without retaining prompts or credentials. A failed
operation stays failed for manual review rather than being retried automatically.

This deliberately narrow mechanism is extensible by adding reviewed typed actions
and their tests. It is not an unrestricted autonomous root agent.

## State and package boundaries

- `/etc/chromax`: root-managed endpoint configuration, optional credentials and
  trusted Ed25519 application-signing keys.
- `/run/chromax/token`: ephemeral HTTP bearer token, readable by the local
  `chromax` account, rotated at daemon restart.
- `/var/lib/chromax`: model blobs, current model metadata, root-owned plans,
  locks and the action audit log.
- `/opt/chromax/apps/<name>/<version>`: verified application bundle files.
  A `current` symlink is atomically replaced to activate or roll back an app.
- `/home/chromax`: ordinary user data and explicitly provisioned SSH public keys.

Application bundles are whole signed archives with a schema-versioned manifest,
architecture, entry point, modes and SHA-256 file digests. They cannot install
files into the base OS, execute maintainer scripts, create symlinks/device nodes,
or set privileged file modes. Signatures are checked against separately
provisioned root-managed trust keys. The installer first copies the archive into
a private staging directory to prevent verification/extraction races.

The base OS is image-managed. Updating its libraries or kernel requires a rebuilt
and qualified image. An app rollback does not roll back the base OS. A/B OS
updates, verified boot and a graphical desktop are separate follow-on engineering
work; they are not implied by application version switching.

## Qualification

There are separate gates for host unit/security tests, source compilation, guest
boot, persistent state, guest networking/TLS, SSH policy, a real local model
response, signed bundle lifecycle, installer safety and release source/license
availability. CI does fast tests on every push; full images are built and tested
on demand. Build artifacts must be identified by hashes and accompanied by the
exact generated configuration. Reproducible-build settings are enabled, but
bit-for-bit reproducibility is only claimed after independent double builds.
