FROM ubuntu:26.04@sha256:6a06111c3b0a8600feadb270aec771dc239bf407b25625f93f44ab00e11f4d3c
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential ca-certificates curl wget git file rsync bc cpio unzip \
    bzip2 xz-utils patch python3 python3-venv libncurses-dev flex bison \
    libssl-dev gawk texinfo help2man autoconf automake libtool pkg-config \
    qemu-system-arm qemu-system-x86 qemu-utils qemu-efi-aarch64 ovmf e2fsprogs dosfstools \
    parted gdisk mtools sudo gnupg zstd && rm -rf /var/lib/apt/lists/*
RUN useradd -m -u 1001 builder
WORKDIR /work
