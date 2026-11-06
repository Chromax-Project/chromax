# Install and try Chromax

Download the architecture-specific assets from the
[public alpha release](https://github.com/Chromax-Project/chromax/releases/tag/v0.1.0-alpha.1).
Use `aarch64` on an Apple Silicon Mac or an ARM64 QEMU host, and `x86_64` for
Intel/AMD PCs. ARM support targets QEMU's `virt` machine; this is not a Raspberry
Pi or Apple bare-metal image. The PC disk image requires UEFI with Secure Boot
disabled. See [qualification status](STATUS.md) for the tested configurations.

## Verify the download

Obtain the source checkout through a trusted channel. The release verification
key is `keys/release.pub` in that checkout. Its DER SHA-256 fingerprint is
`2a58f67e52085190627772f5e97353c604767b04c106ba0b5adb66261dc6a2a3`.

In a directory containing the downloaded assets, verify the signature and every
downloaded asset against the signed manifest. For example, with OpenSSL 3 and
GNU `sha256sum`:

```sh
openssl pkeyutl -verify -pubin -inkey /path/to/chromax/keys/release.pub -rawin \
  -in chromax-0.1.0-aarch64-SHA256SUMS \
  -sigfile chromax-0.1.0-aarch64-SHA256SUMS.sig
sha256sum -c chromax-0.1.0-aarch64-SHA256SUMS
```

The full manifest includes the source/license and configuration assets. Download
those too to check the entire manifest. Keep them when redistributing images.
A verification key downloaded only beside the images does not independently
establish publisher identity.

## Start a virtual machine

Install QEMU and Zstandard on the host. Extract the rootfs with its expected name,
then copy the architecture's kernel beside it. For ARM64:

```sh
mkdir -p images/aarch64
zstd -d chromax-0.1.0-aarch64-rootfs.ext4.zst -o images/aarch64/rootfs.ext4
cp chromax-0.1.0-aarch64-Image images/aarch64/Image
/path/to/chromax/scripts/run-vm.sh aarch64 images/aarch64
```

For x86-64, substitute `x86_64` and use the `bzImage` kernel asset. The script
creates a persistent qcow2 overlay in `.cache/vm-ARCH`; the downloaded master
stays unchanged. ARM guests use HVF automatically on Apple Silicon. Matching
Linux hosts use KVM when the current user can access `/dev/kvm`; other hosts use
QEMU's software emulation. Software inference can be slow. Stop the guest with
`sudo chromaxctl poweroff`.

The local console opens the `chromax` administrator account. It starts without
passwords or SSH keys. Provision your own key before connecting remotely:

```sh
chromaxctl status
chromaxctl doctor
sudo chromaxctl ssh-key 'ssh-ed25519 YOUR_PUBLIC_KEY your-comment'
```

The VM forwards SSH to host loopback port 2222. From the host, use
`ssh -p 2222 chromax@127.0.0.1`. Root SSH and SSH password login are disabled.

## Enable local AI

Weights are deliberately separate from the OS. The tested fixture is the
publisher's [Qwen3-0.6B Q8_0 GGUF](https://huggingface.co/Qwen/Qwen3-0.6B-GGUF),
revision `23749fefcc72300e3a2ad315e1317431b06b590a`, SHA-256
`9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031`.
Check its Apache-2.0 license and model card. It is a small integration model,
not a guarantee of correct administration advice.

Copy the model to the running guest:

```sh
scp -O -P 2222 Qwen3-0.6B-Q8_0.gguf chromax@127.0.0.1:/home/chromax/
```

Then, in the guest:

```sh
sudo chromaxctl model add /home/chromax/Qwen3-0.6B-Q8_0.gguf \
  --sha256 9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031
chromaxctl plan service-restart inference
sudo chromaxctl apply RETURNED_ID --confirm RETURNED_ID
ai ask 'Give me a brief system health check.'
ai propose 'Set the hostname to studio'
```

Review every pending plan before applying its exact ID. The assistant cannot
execute shell commands or apply its own proposals. A separate interactive
`sudo chromaxctl admin` opens a root shell for manual administration.
After successful provisioning, the original model in `/home/chromax` may be
removed to reclaim space; the content-addressed installed copy remains.

For the browser console, run `chromaxctl web-token` in the guest, then forward
its loopback service from the host:

```sh
ssh -p 2222 -L 8080:127.0.0.1:8080 chromax@127.0.0.1
```

Open `http://127.0.0.1:8080` and enter the token. Chat, metrics, and pending plans
are available there. Applying plans still requires the local CLI.

## Install a UEFI disk image

The `chromax.img.zst` asset contains a GPT disk, an EFI system partition and a
4 GiB ext4 root partition. It can also be used as a disposable VM disk with UEFI
firmware. Decompress it to `chromax.img`, then verify its uncompressed checksum
against `UNCOMPRESSED_SHA256SUMS`.

For a physical installation, boot a trusted Linux recovery environment containing
Python 3 and util-linux. Inspect the available disks and back up the chosen target.
The installer overwrites that entire target. It does not select a disk for you.
Never target the external drive holding your build or download files.

```sh
PYTHONPATH=/path/to/chromax/src python3 -m chromax.installer chromax.img /dev/CHOSEN_DISK \
  --sha256 PUBLISHED_UNCOMPRESSED_IMAGE_SHA256
```

The first invocation is a dry run. Review its resolved target, size and effect.
To perform the installation, run the same command as root and append
`--confirm /dev/CHOSEN_DISK` using the exact resolved whole-disk path. Mounted
targets and partitions are rejected. The installer hashes the source, writes the
image, flushes it and verifies the bytes read back from the target. Reboot into
UEFI. Larger disks retain unused space; see the installer output before manually
relocating the backup GPT header and growing the partition/filesystem.

Physical hardware has not been certified. The alpha has no graphical desktop,
Secure Boot chain, disk-encryption setup or automatic base-OS updater. Retain a
recovery medium and consult the [handbook](HANDBOOK.md) for backups and updates.
