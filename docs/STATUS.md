# Execution and release status

Updated: 2026-11-05. Work is active; this file distinguishes implementation from
executed evidence.

| Gate | Status | Evidence |
|---|---|---|
| Research and architecture | Written | `RESEARCH.md`, `ARCHITECTURE.md` |
| Public source repository | Created | https://github.com/Chromax-Project/chromax |
| Source archive integrity | Buildroot verified | SHA-256 matched signed release statement; maintainer PGP signature checked |
| Target source compilation | Running: ARM64 | External-drive build log; no completed image yet |
| Host security and unit tests | 27 passed locally; GitHub checks also passing | `scripts/test.sh`; [GitHub checks](https://github.com/Chromax-Project/chromax/actions) |
| Guest boot, networking and persistence | Pending | Requires source-built image |
| Guest local-model inference | Pending | Checksummed GGUF fixture downloaded |
| Signed app install/upgrade/rollback | Host test implemented | Guest qualification pending |
| UEFI images and installer | In progress | Disk-image recipe implemented; boot validation pending |
| x86-64 qualification | Pending | Configuration implemented |
| Source/license release bundle | Pending | Build script invokes `legal-info` |
| Public binary release | Pending | Only qualified artifacts will be released |

## Material limits

There is no general graphical desktop, A/B base-OS updater, disk encryption setup,
Secure Boot chain, automatic vulnerability remediation, or hardware certification
yet. The initial base image is writable ext4. The app manager supports self-contained
bundles; it does not resolve arbitrary dependency graphs. These are explicit
boundaries, not completed features.
