# Source and license distribution

Chromax's original code is MIT licensed (`LICENSE` and `src/LICENSE`). Upstream
components retain their own licenses. Linux and BusyBox are GPLv2, GRUB is GPLv3,
musl is MIT, Python uses the PSF license, and other selected packages have their
own notices. This summary is not an exhaustive bill of materials.

Every binary release must retain the exact Buildroot configuration and include
the generated `legal-info` material. `make legal-info` gathers source archives,
patches, license files and manifests into the output directory. Review its
warnings; collection alone is not a legal-compliance certification. The Chromax
external-tree source and upstream Buildroot source are also required to reproduce
the binary. Host and target material are distinguished in Buildroot's manifests.

The release process will publish corresponding sources alongside images rather
than rely solely on a written offer. Archive hashes bind the release assets to
their source/configuration records. Do not remove source assets while the
corresponding binaries remain distributed.

Model weights are not included in base images. Model licensing is separate from
llama.cpp and the OS. The small inference integration fixture is declared
Apache-2.0 by its publisher; its revision and checksum are in `RESEARCH.md`.
Users must check licenses and suitability for the models they provision.
