# Chromax Linux

**Your machine, understood.** Chromax is an independent, source-built Linux system
with an integrated local AI interface. The kernel, musl userspace, command-line
tools and inference engine are compiled from upstream source. No parent
distribution's root filesystem or package repositories are used in the resulting
image. Buildroot orchestrates the build; Ubuntu is only the isolated build host.

**Development status:** implementation and release qualification are in progress.
Do not infer a working image from a passing application test. Executed checks and
remaining gates are recorded in [docs/STATUS.md](docs/STATUS.md).

## What Chromax includes

- Linux 6.18.60, musl, BusyBox init and shell, DHCP, TLS trust, curl, Git, SSH,
  sudo, nano, htop, filesystem and networking tools.
- `ai ask` and `ai chat`, with a fresh system snapshot for each question.
- A browser console with system metrics, AI chat and reviewable system plans.
- CPU inference through a source-built llama.cpp server and explicit GGUF model
  provisioning. Remote compatible endpoints require an explicit HTTPS opt-in.
- Named administrative plans with a 15-minute lifetime, explicit local approval,
  replay protection and an audit log. AI output is never executed as shell code.
- Signed application bundles, payload verification, version selection and atomic
  application rollback. Base-system changes are made by rebuilding an image.
- ARM64 virtual-machine and x86-64 UEFI configurations, reproducible-build
  settings, license/source collection and automated qualification scripts.

This is a console/server distribution with a browser management interface. It does
not currently include a graphical Linux desktop. Model accuracy, hardware support
and secure deployment are separate qualification concerns.

## Build

Docker and about 40 GiB of actual free build storage are recommended. The build
uses a sparse 96 GiB ext4 file on the storage volume, so case-insensitive macOS
filesystems work correctly. It never reformats the external drive.

```sh
git clone https://github.com/Chromax-Project/chromax.git
cd chromax
export CHROMAX_STORAGE=/path/to/build-storage
./scripts/build.sh aarch64
./scripts/build.sh x86_64
./scripts/test.sh
```

The default local storage path is `/Volumes/Models/Chromax`. Build jobs default to
six; set `CHROMAX_JOBS` to change this. Build both architectures **sequentially**:
the ext4 workspace must never be mounted by two build containers simultaneously.

Outputs are written to `$CHROMAX_STORAGE/artifacts/<architecture>/`. The disk
image is `chromax.img`; the kernel and standalone rootfs are also retained.
`legal-info.tar` contains collected source archives, patches and license texts.

## Use the system

The local serial console enters the unprivileged `chromax` account. Root and user
passwords are locked in the image. SSH rejects root and password authentication.
The local console grants administrative access through the constrained
`chromaxctl` entry point, so protect physical/VM console access.

```sh
chromaxctl status
chromaxctl doctor
chromaxctl web-token
sudo chromaxctl ssh-key 'ssh-ed25519 AAAA... your-key-comment'
sudo chromaxctl passwd
```

Provision a GGUF model that you are licensed to use:

```sh
sudo chromaxctl model add /path/to/model.gguf --sha256 YOUR_64_CHARACTER_CHECKSUM
chromaxctl plan service-restart inference
# Review the returned plan, then run its exact apply command.
ai ask 'Give me a brief health check of this machine.'
```

The browser console listens on `127.0.0.1:8080` by default. Forward it over an SSH
tunnel or deliberately enable a network listener through `chromaxctl config`.
Its access token stays in browser memory and is regenerated on service restart.
Use a TLS reverse proxy or SSH tunnel on an untrusted network. The inference
endpoint remains on loopback.

```sh
chromaxctl plan hostname chromax-studio
chromaxctl show PLAN_ID
sudo chromaxctl apply PLAN_ID --confirm PLAN_ID
```

See [the handbook](docs/HANDBOOK.md), [architecture](docs/ARCHITECTURE.md),
[research and source decisions](docs/RESEARCH.md), and
[security model](docs/SECURITY.md).

## Licensing

Original Chromax code is MIT licensed. The distributed system contains separately
licensed upstream components, including GPL Linux and BusyBox. The MIT license
does not replace those licenses. Corresponding sources and license information
must accompany binary releases. Models have their own licenses and are not
included in the base image. See [docs/LICENSING.md](docs/LICENSING.md).
