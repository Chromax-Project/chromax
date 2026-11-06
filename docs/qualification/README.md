# Executed qualification evidence

These reports come from actual source-built guests, not host-side mocks.
`source_image_sha256` identifies the pristine release master. Every guest ran
from a disposable writable copy; test keys, model weights, plans and installed
test applications are absent from the release masters.

The ARM64 and UEFI reference environment was an Apple Silicon macOS host with
QEMU 11.1.3, 2 virtual CPUs and 2 GiB guest RAM. ARM64 used HVF. x86-64 UEFI used
TCG software emulation. UEFI tests used QEMU's EDK2 firmware; x86 firmware code
and a disposable variable store were attached as separate pflash devices. The
image's GRUB loaded the kernel and located the root partition by its UUID.

The full x86-64 model run used an Ubuntu 24.04 GitHub runner with KVM, QEMU 8.2.2,
2 guest vCPUs and 2 GiB guest RAM. Its [workflow run](https://github.com/Chromax-Project/chromax/actions/runs/42134368926)
downloaded the signed candidate, verified its compressed and raw-image hashes,
checked the model's exact hash, and passed all 13 gates. The earlier TCG run
produced text but exceeded the integrated assistant's deadline; KVM qualification
retained that deadline.

The direct-boot model fixture was Qwen3-0.6B Q8_0, SHA-256
`9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031`.
The model generated a real response through llama.cpp, answered through `ai ask`,
and translated a hostname request into the correct pending typed plan. Model
selection and automatic inference startup were checked again after reboot.
The UEFI matrix checks the nine base-system gates without model weights.

`native management tools` confirms CLI execution. The initial diagnostic output
may report absent weights or a broker still starting; later gates explicitly
require the authenticated broker and, in model runs, an operational inference
backend. Missing weights in an unprovisioned base image are expected.

The original 60-second model-copy limit was too short during concurrent external
drive I/O. Final runs allow 300 seconds for copying and hashing weights. Inference
and semantic intent checks retain their separate bounded timeouts. A smaller
135M model's incorrect intent proposal was rejected during development; see
[the research record](../RESEARCH.md).

The installer test targets a newly allocated file-backed Linux loop device. It
hashes the final GPT image, writes the complete disk, flushes it, and hashes the
bytes read back. No physical disk was overwritten. Virtual-machine qualification
does not establish physical-hardware compatibility, production security, broad
model accuracy or independent bit-identical rebuilds.

To reproduce, build an architecture, run `scripts/prepare-qualification.sh` in
the privileged builder environment, then invoke `scripts/qualify.py` against its
disposable copy. `--accelerator`, `--uefi`, `--firmware-path`, `--firmware-vars`
and `--ssh-port` select the host environment. See `--help` and the script's fixed
checks. `scripts/qualify-uefi.sh` combines the loop-device installer with a UEFI
test in the Linux builder.
