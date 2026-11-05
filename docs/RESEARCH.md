# Research and upstream decisions

Checked 2026-11-05. Links below are primary upstream sources; versions are pinned
in configurations rather than resolved dynamically at build time.

| Question | Evidence | Decision |
|---|---|---|
| Kernel series | [kernel.org releases](https://www.kernel.org/releases.html) and [machine-readable release index](https://www.kernel.org/releases.json) list 6.18 as longterm and 6.18.60 as its current release on the research date. | Pin 6.18.60 rather than a release candidate. Store the archive SHA-256 from kernel.org's signed checksum listing. Follow upstream security updates through explicit reviewed version changes. |
| Build from source | [Buildroot manual](https://buildroot.org/downloads/manual/manual.html), chapters 1, 9 and 18, describes generating a cross-toolchain, kernel, bootloader and rootfs, plus an external tree for downstream customization. | Use an external tree. No Debian/Ubuntu/Alpine rootfs inheritance. Build host dependencies are separate from target contents. |
| Build system release | [Buildroot downloads](https://buildroot.org/download.html) lists 2026.08.1 as stable. Its signed release notice gives SHA-256 `34fb7bea8a213ffde39cc02e61703391560f26e0850f03138c722d0b09880f2b`. | Pin 2026.08.1; compare the archive hash to the verified signed notice. Maintainer-key fingerprint used: `18C7 DF28 19C1 733D 822D 599E A500 D6EE 9CB0 E540`, fetched through the release's upstream key link. This is upstream-key verification, not an independently established personal trust chain. |
| Minimal userspace | [BusyBox upstream](https://www.busybox.net/about.html) describes modular Unix utilities and a small Linux runtime, licensed GPLv2. | BusyBox init and utilities, musl libc, and additional standalone tools where useful. Keep Python for a small auditable management implementation. |
| Inference runtime | [llama.cpp server](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md) supports CPU GGUF inference and a compatible chat API. Buildroot already carries a checksummed llama.cpp b8117 recipe. | Reuse that pinned recipe; disable host-native instruction tuning and OpenMP. Keep the model process unprivileged and loopback-only. No dependency on a cloud AI provider. |
| Packages | [Buildroot manual §11.7](https://buildroot.org/downloads/manual/manual.html#faq-no-binary-packages) explains why Buildroot does not supply ordinary binary package management. | Keep the base image coherent. Add a separate signed app-bundle format, with strict paths, architecture checks, file digests and atomic activation. Do not present this as Debian/RPM package compatibility. |
| Bootloader | [GNU GRUB manual](https://www.gnu.org/software/grub/manual/grub/grub.html) documents UEFI boot and partition discovery. | Source-built GRUB, GPT, FAT ESP and kernel root partition UUID. Secure Boot signing is not part of the initial release. |
| Model test fixture | [SmolLM2 model card](https://huggingface.co/HuggingFaceTB/SmolLM2-135M-Instruct) supplies the upstream model; [bartowski's GGUF repository](https://huggingface.co/bartowski/SmolLM2-135M-Instruct-GGUF) supplies the quantized artifact. | Test real inference with Q8_0, revision `09816acd5d99df7be770d85ea30822623dab342c`, SHA-256 `5a1395716f7913741cc51d98581b9b1228d80987a9f7d3664106742eb06bba83`, 144,811,360 bytes. Its declared license is Apache-2.0. It is a small integration fixture, not evidence of strong administration reasoning. Models remain outside the base OS. |

## Alternatives considered

Linux From Scratch provides an educational manual build path but would require
maintaining equivalent build orchestration and source tracking before repeatable
image production. Yocto offers a powerful layer ecosystem at substantially
greater initial build and metadata cost. NixOS and conventional distro remixes
would inherit a wider distribution platform, contrary to the desired independent
base. Buildroot gives the smallest established path to compiling the whole target
while leaving Chromax policy and the interface independent.

Systemd would bring a large service-management ecosystem. BusyBox init is used for
the first coherent system because there are few services; restart/status behavior
is explicitly tested. The design does not claim systemd API compatibility.

An unrestricted AI shell would provide more apparent capability but make model
output part of the privilege boundary. Typed operations are chosen so trust stays
in reviewed system code. Model suggestions cannot expand the list of operations.
