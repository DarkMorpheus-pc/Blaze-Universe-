#!/usr/bin/env bash
# ==============================================================================
# Blaze Universe — Minimal Vanilla Linux Kernel & Initramfs Builder (Linux 7.2.8)
# ==============================================================================
set -euo pipefail

BLAZE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK_DIR="${BLAZE_ROOT}/build/kernel_7.2_work"
SOURCES_DIR="${BLAZE_ROOT}/build/sources"
PKGS_DIR="${BLAZE_ROOT}/build/packages"
BUILDER="${BLAZE_ROOT}/target/debug/blaze-builder"

KERNEL_VER="7.2.8"
KERNEL_TAR="linux-${KERNEL_VER}.tar.xz"
JOBS="${JOBS:-$(nproc)}"

mkdir -p "${WORK_DIR}" "${SOURCES_DIR}" "${PKGS_DIR}"

# 1. Extract
if [ ! -d "${WORK_DIR}/linux-${KERNEL_VER}" ]; then
    echo "Extracting ${KERNEL_TAR}..."
    tar -xf "${SOURCES_DIR}/${KERNEL_TAR}" -C "${WORK_DIR}"
fi

cd "${WORK_DIR}/linux-${KERNEL_VER}"

# 2. Check for versioned patches
PATCH_DIR="${BLAZE_ROOT}/recipes/core/linux-blaze/patches"
if [ -d "${PATCH_DIR}" ]; then
    for p in "${PATCH_DIR}"/*.patch; do
        if [ -f "$p" ]; then
            echo "Applying patch: $p"
            patch -Np1 -i "$p" || true
        fi
    done
fi

# 3. Configure kernel
echo "Configuring minimal linux-blaze kernel (7.2.8)..."
make x86_64_defconfig

./scripts/config --enable CONFIG_VIRTIO
./scripts/config --enable CONFIG_VIRTIO_PCI
./scripts/config --enable CONFIG_VIRTIO_BLK
./scripts/config --enable CONFIG_VIRTIO_NET
./scripts/config --enable CONFIG_VIRTIO_CONSOLE
./scripts/config --enable CONFIG_EXT4_FS
./scripts/config --enable CONFIG_DEVTMPFS
./scripts/config --enable CONFIG_DEVTMPFS_MOUNT
./scripts/config --enable CONFIG_SERIAL_8250
./scripts/config --enable CONFIG_SERIAL_8250_CONSOLE
./scripts/config --enable CONFIG_EFI
./scripts/config --enable CONFIG_EFI_STUB
./scripts/config --enable CONFIG_EFIVAR_FS
./scripts/config --enable CONFIG_TMPFS
./scripts/config --enable CONFIG_TMPFS_POSIX_ACL
./scripts/config --enable CONFIG_CGROUPS
./scripts/config --enable CONFIG_NAMESPACES
./scripts/config --enable CONFIG_SECCOMP
./scripts/config --enable CONFIG_SECCOMP_FILTER
./scripts/config --enable CONFIG_BINFMT_ELF
./scripts/config --enable CONFIG_BINFMT_SCRIPT
./scripts/config --enable CONFIG_OVERLAY_FS
./scripts/config --enable CONFIG_AUTOFS_FS
./scripts/config --enable CONFIG_FHANDLE
./scripts/config --enable CONFIG_DMIID
./scripts/config --enable CONFIG_BLK_DEV_INITRD
./scripts/config --enable CONFIG_RD_GZIP
./scripts/config --enable CONFIG_PARTITION_ADVANCED
./scripts/config --enable CONFIG_EFI_PARTITION
./scripts/config --set-str CONFIG_DEFAULT_HOSTNAME "blaze"

# Speed up build
./scripts/config --disable CONFIG_DEBUG_INFO
./scripts/config --disable CONFIG_DEBUG_INFO_BTF
./scripts/config --disable CONFIG_DEBUG_INFO_DWARF_TOOLCHAIN_DEFAULT

make olddefconfig

# 4. Compile bzImage
echo "Compiling bzImage 7.2.8 (Jobs: ${JOBS})..."
make -j"${JOBS}" bzImage

# 5. Assemble package DESTDIR for linux-blaze
KERNEL_DEST="${WORK_DIR}/kernel-dest"
rm -rf "${KERNEL_DEST}"
mkdir -p "${KERNEL_DEST}/boot"

cp arch/x86/boot/bzImage "${KERNEL_DEST}/boot/vmlinuz-linux"
chmod 0755 "${KERNEL_DEST}/boot/vmlinuz-linux"

# 6. Generate robust static initramfs (cpio archive)
INITRAMFS_WORK="${WORK_DIR}/initramfs_work"
rm -rf "${INITRAMFS_WORK}"
mkdir -p "${INITRAMFS_WORK}"/{bin,dev,proc,sys,mnt,root,etc,run}

cat << 'EOF_INIT' > "${INITRAMFS_WORK}/init.c"
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/types.h>

int main(int argc, char *argv[]) {
    (void)argc; (void)argv;
    printf("\n===============================================\n");
    printf("   BlazeOS Native — Early Boot Initramfs (7.2.8)\n");
    printf("===============================================\n\n");

    mount("proc", "/proc", "proc", 0, NULL);
    mount("sysfs", "/sys", "sysfs", 0, NULL);
    mount("devtmpfs", "/dev", "devtmpfs", 0, NULL);
    mount("tmpfs", "/run", "tmpfs", 0, NULL);

    const char *candidates[] = {
        "/dev/disk/by-partuuid/44444444-4444-4444-4444-444444444444",
        "/dev/disk/by-partlabel/blaze-root",
        "/dev/vda2",
        "/dev/sda2",
        "/dev/nvme0n1p2",
        NULL
    };

    const char *root_dev = NULL;
    printf("[INIT] Waiting for root block device...\n");
    for (int retry = 0; retry < 50; retry++) {
        for (int i = 0; candidates[i]; i++) {
            struct stat st;
            if (stat(candidates[i], &st) == 0 && S_ISBLK(st.st_mode)) {
                root_dev = candidates[i];
                break;
            }
        }
        if (root_dev) break;
        usleep(100000);
    }

    if (!root_dev) {
        printf("[FATAL] Could not find root partition!\n");
        while(1) sleep(10);
    }

    printf("[INIT] Found root block device: %s\n", root_dev);
    printf("[INIT] Mounting %s to /mnt (ext4)...\n", root_dev);

    mkdir("/mnt", 0755);
    if (mount(root_dev, "/mnt", "ext4", MS_RELATIME, NULL) != 0) {
        perror("[FATAL] mount /mnt failed");
        while(1) sleep(10);
    }

    printf("[INIT] Moving virtual filesystems to new root...\n");
    mkdir("/mnt/proc", 0755);
    mkdir("/mnt/sys", 0755);
    mkdir("/mnt/dev", 0755);
    mkdir("/mnt/run", 0755);

    mount("/proc", "/mnt/proc", NULL, MS_MOVE, NULL);
    mount("/sys", "/mnt/sys", NULL, MS_MOVE, NULL);
    mount("/dev", "/mnt/dev", NULL, MS_MOVE, NULL);
    mount("/run", "/mnt/run", NULL, MS_MOVE, NULL);

    printf("[INIT] Switching root to BlazeOS systemd...\n");
    chdir("/mnt");
    mount(".", "/", NULL, MS_MOVE, NULL);
    chroot(".");
    chdir("/");

    char *target_argv[] = { "/usr/lib/systemd/systemd", NULL };
    char *target_envp[] = { "HOME=/root", "TERM=linux", "PATH=/usr/bin:/usr/sbin", NULL };

    execve("/usr/lib/systemd/systemd", target_argv, target_envp);
    perror("[FATAL] execve systemd failed");
    while(1) sleep(10);
    return 1;
}
EOF_INIT

gcc -static -O2 "${INITRAMFS_WORK}/init.c" -o "${INITRAMFS_WORK}/init"
rm -f "${INITRAMFS_WORK}/init.c"
chmod 0755 "${INITRAMFS_WORK}/init"

(cd "${INITRAMFS_WORK}" && find . -print0 | cpio --null -ov --format=newc | gzip -9 > "${KERNEL_DEST}/boot/initramfs-linux.img")

# 7. Package linux-blaze 7.2.8
cat << 'EOF_RECIPE' > "${BLAZE_ROOT}/recipes/core/linux-blaze/recipe.toml"
[package]
name = "linux-blaze"
version = "7.2.8"
release = 1
architecture = "x86_64"
summary = "Vanilla Linux kernel 7.2.8 for BlazeOS Native"
license = "GPL-2.0-only"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://kernel.org"

[dependencies]
provides = ["kernel", "linux = 7.2.8"]

[build]
script = """
cp -a "$CURRENT_DIR/build/kernel_7.2_work/kernel-dest/"* "$DESTDIR/"
"""
EOF_RECIPE

"${BUILDER}" "${BLAZE_ROOT}/recipes/core/linux-blaze/recipe.toml"

# 8. Assemble and Package linux-api-headers 7.2.8
echo "Installing and packaging linux-api-headers 7.2.8..."
HDR_DEST="${WORK_DIR}/headers-dest"
rm -rf "${HDR_DEST}"
mkdir -p "${HDR_DEST}/usr"
make ARCH=x86_64 INSTALL_HDR_PATH="${HDR_DEST}/usr" headers_install

mkdir -p "${BLAZE_ROOT}/recipes/core/linux-api-headers"
cat << 'EOF_HDR_RECIPE' > "${BLAZE_ROOT}/recipes/core/linux-api-headers/recipe.toml"
[package]
name = "linux-api-headers"
version = "7.2.8"
release = 1
architecture = "x86_64"
summary = "Linux API kernel headers for userspace development"
license = "GPL-2.0-only"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://kernel.org"

[dependencies]
provides = ["linux-api-headers = 7.2.8"]

[build]
script = """
cp -a "$CURRENT_DIR/build/kernel_7.2_work/headers-dest/"* "$DESTDIR/"
"""
EOF_HDR_RECIPE

"${BUILDER}" "${BLAZE_ROOT}/recipes/core/linux-api-headers/recipe.toml"

echo "=== Linux 7.2.8 & Headers Packages Built Successfully ==="
