# Chromax handbook

## Boot and first access

The ARM64 kernel and ext4 rootfs can be booted directly with QEMU's `virt` machine.
The GPT image is intended for UEFI firmware. x86-64 uses UEFI; legacy BIOS is not
configured. Keep the original image immutable on the host and use a VM overlay or
working copy for experiments. A serial console auto-enters `chromax`, with
passwords locked and SSH keys initially absent.

The base is writable ext4. Normal state persists across reboots. The disk-image
installer replaces a whole target disk and must only be used on an explicitly
selected empty/disposable device. It never chooses a disk automatically. Do not
write a disk image onto the external drive containing your build storage.

`chromaxctl status` works without a model. `chromaxctl doctor` distinguishes missing
inference weights from base-system health. Use `sudo chromaxctl ssh-key '...full
public key...'` to authorize the `chromax` SSH account. Root SSH and SSH passwords
remain disabled. `sudo chromaxctl passwd` sets the user's console password for
future password-authenticated workflows; the development serial console still
uses auto-login.

## Local AI

Copy a trusted GGUF model into the guest or attach a separate model volume. Verify
the publisher, revision, checksum, license and hardware requirements. The small
SmolLM2 integration fixture described in `RESEARCH.md` is for testing and is not a
strong administration model. A larger compatible model can be provisioned with
the same interface.

```sh
sudo chromaxctl model add /mnt/model.gguf --sha256 CHECKSUM
chromaxctl plan service-restart inference
sudo chromaxctl apply RETURNED_ID --confirm RETURNED_ID
ai ask 'What is my current memory usage?'
ai chat
```

The model file is stored under its content hash. Provisioning replaces the current
model link only after the entire file passes hash/header checks. Restart inference
after selecting a new model. Old blobs are retained for manual recovery.

To use a compatible remote endpoint:

```sh
sudo chromaxctl config --endpoint https://your-provider.example/v1 \
  --model your-model --allow-remote --api-key
```

The key is read privately from the terminal into a root-only credential file.
Remote use sends the question and system snapshot described in `ARCHITECTURE.md`.
Return to local inference with:

```sh
sudo chromaxctl config --endpoint http://127.0.0.1:8081/v1 --model local
```

## Browser console

Run `chromaxctl web-token` on the guest. Reach loopback port 8080 through an SSH
tunnel, then enter that token into the browser console. For example, from another
machine with a provisioned SSH key:

```sh
ssh -L 8080:127.0.0.1:8080 chromax@GUEST_ADDRESS
```

Open `http://127.0.0.1:8080`. No token is embedded in the page or saved to browser
storage. Refreshing the page requires reconnecting. Service restart rotates the
token. A deliberate network listener can be configured with `--listen 0.0.0.0`
alongside the other `chromaxctl config` options, then a console service restart is
required. Never expose cleartext bearer-token traffic to an untrusted network.

The console can prepare plans, but applying them happens in the local CLI:

```sh
chromaxctl plan hostname studio
chromaxctl show PLAN_ID
sudo chromaxctl apply PLAN_ID --confirm PLAN_ID
```

Plans expire after 15 minutes and cannot be applied twice. Restart operations are
limited to `network`, `ssh`, `inference` and `console`. The assistant does not automatically
execute a model-generated instruction.

## Application bundles

An app is a self-contained directory with an executable entrypoint. Compile
native binaries against the matching Chromax toolchain, or use scripts supported
by the base system. Shared-library dependencies are the app publisher's
responsibility; arbitrary distro packages are not interchangeable.

On a development machine:

```sh
PYTHONPATH=src python3 -m chromax.cli package build ./hello hello.cxpk \
  --name hello --version 1.0.0 --architecture all --entrypoint bin/hello
openssl genpkey -algorithm ED25519 -out publisher-private.pem
openssl pkey -in publisher-private.pem -pubout -out publisher-public.pem
openssl pkeyutl -sign -inkey publisher-private.pem -rawin \
  -in hello.cxpk -out hello.cxpk.sig
```

Keep the private signing key outside repositories and release assets. On the guest,
provision a public key separately from the untrusted bundle:

```sh
sudo chromaxctl package trust publisher publisher-public.pem
sudo chromaxctl package install hello.cxpk --signature hello.cxpk.sig --key publisher
chromaxctl package list
chromaxctl package run hello
sudo chromaxctl package rollback hello 1.0.0
```

The installer accepts only signed regular files, validates each payload hash, and
does not execute scripts during installation. A bundle runs as the invoking user;
running application bundles through sudo is rejected. Rolling back changes the
current version pointer. It does not undo an app's writes to user data.

## Base updates, recovery and backups

Kernel/libc/base-tool changes require a new source build and qualification. The
first release has no automatic in-place or A/B base updater. Back up `/home`,
`/etc/chromax`, `/var/lib/chromax` and `/opt/chromax/apps` before replacing an image.
Treat credentials and audit data as private. Do not include them in public bug
reports or images.

Use the original host-side image to recover a broken guest, or attach its rootfs
to a separate recovery VM. Review failed plans in `/var/lib/chromax/plans` and the
action audit at `/var/lib/chromax/audit.jsonl`. Prompt text is not logged by the
Chromax broker. Inference and console service startup logs live under
`/var/log/chromax`; inspect these when `doctor` reports an unavailable backend.

## Extending the base

Buildroot's package catalog is available through the external-tree configuration.
Change the relevant `configs/chromax_*_defconfig`, rebuild, and retain the exact
generated configuration and legal/source material. Adding a service or privileged
action requires an explicit implementation and boundary tests. Updating the kernel
also requires updating its custom archive checksum. Do not silently resolve
latest versions during a reproducible build.

If the console daemon is stopped, run `sudo chromaxctl recover` from the local
console. This narrowly restarts the broker without requiring its HTTP API.

For full manual administration, use `sudo chromaxctl admin` in an interactive
terminal. It opens a root shell; `exit` returns to the user account. This is an
explicit administrator workflow and is never exposed through the assistant API.
Use `sudo chromaxctl poweroff` or `sudo chromaxctl reboot` for power management.
