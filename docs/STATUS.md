# Execution and release status

Updated: 2026-11-05. Chromax 0.1.0 is an initial experimental console/server
distribution with a browser management interface. The target system is compiled
from upstream source; no parent distribution rootfs is inherited.

| Gate | Executed result | Evidence |
|---|---|---|
| Research and architecture | Complete | [Research](RESEARCH.md), [architecture](ARCHITECTURE.md) |
| Public source | Public in Chromax Project | [Repository](https://github.com/Chromax-Project/chromax) |
| Upstream source integrity | Buildroot hash and signed release notice verified; kernel hash verified | [Research record](RESEARCH.md), build driver and custom kernel hash |
| ARM64 and x86-64 source compilation | Both complete | Exact Buildroot, Linux and BusyBox configurations, package inventory and CycloneDX SBOM accompany the images |
| Policy, HTTP, package and installer unit tests | 30 passed in Linux; GitHub checks passed | `scripts/test.sh`, [Actions](https://github.com/Chromax-Project/chromax/actions) |
| ARM64 direct boot, including local AI | 13 of 13 gates passed, HVF | [Report](qualification/aarch64-direct.json) |
| ARM64 UEFI/GRUB boot | 9 of 9 base gates passed, HVF | [Report](qualification/aarch64-uefi.json) |
| x86-64 UEFI/GRUB boot | 9 of 9 base gates passed, TCG | [Report](qualification/x86_64-uefi.json) |
| x86-64 direct boot, including local AI | 13 of 13 gates passed, KVM | [Report](qualification/x86_64-direct.json), [executed workflow](https://github.com/Chromax-Project/chromax/actions/runs/42134368926) |
| Whole-disk installer | Full final x86 image written and readback hash matched on a file-backed loop device | [Installer evidence](qualification/installer-x86_64.txt) |
| Clean release masters | Passed | No test fixtures, models, authorized keys, broker tokens or SSH host keys; root password locked |
| Corresponding source and licenses | Collected for both architectures | legal-info, Buildroot source and Chromax source archives accompany binaries |
| Public binary release | Signed initial alpha, with source/license bundles | [Release](https://github.com/Chromax-Project/chromax/releases/tag/v0.1.0-alpha.1) |

The nine base gates cover unprivileged boot, management tools, DHCP/DNS/verified
HTTPS, authenticated HTTP, locked root credentials, plan application and replay
rejection, SSH key login and root rejection, signed application
install/upgrade/execution/rollback, and persistence across a second boot.
The 13-gate run also provisions a checksummed GGUF, executes actual llama.cpp
inference, checks the integrated assistant and correct intent translation, then
verifies model persistence and automatic inference startup after reboot.

See [the evidence notes](qualification/README.md) for test environment, limits and
reproduction. Qualified raw-image hashes are embedded in the JSON reports and
bound to compressed release assets through signed checksum manifests. Release
packaging decompresses and hashes each image, comparing it with the build's
measured raw-image hash. The public verification key is in `keys/release.pub`.

## Material limits

Qualification targets QEMU's ARM64 virt and x86-64 q35 machines with virtio
storage/networking, 2 vCPUs and 2 GiB RAM. ARM firmware testing found and fixed an
EFI clock initialization bug; final firmware boots pass verified HTTPS. The PC
kernel includes built-in NVMe and AHCI root drivers, but physical PCs, Wi-Fi,
GPU support and arbitrary ARM boards have not been certified.

Cross-architecture x86 TCG emulation produced a direct model response but exceeded
the integrated assistant's request deadline. Full x86 model qualification uses a
native x86 Linux runner with KVM, retaining the same request time limits.

There is no graphical Linux desktop, A/B base-OS updater, disk-encryption setup,
Secure Boot chain, automatic vulnerability remediation or established security
support window. The initial base image is writable ext4 with a 4 GiB root
partition. The app manager supports self-contained signed bundles, without a
general dependency solver. Local console/SSH access to the administrator account
is a privileged trust decision. See [the security model](SECURITY.md).

Model weights remain separate and require explicit provisioning. A successful
fixture request does not establish broad model reliability. Reproducible-build
settings and pinned upstream sources are present; an independent bit-identical
second build has not been demonstrated. This release is intended for evaluation
and further development, with backups and a recovery path.
