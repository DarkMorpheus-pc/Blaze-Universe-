#!/usr/bin/env bash
# ==============================================================================
# Blaze Universe — Kernel 7.2.9 & BERP Core Initramfs Builder
# ==============================================================================
set -euo pipefail

BLAZE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK_DIR="${BLAZE_ROOT}/build/kernel_7.2.9_work"
SOURCES_DIR="${BLAZE_ROOT}/build/sources"
PKGS_DIR="${BLAZE_ROOT}/build/packages"
BUILDER="${BLAZE_ROOT}/target/debug/blaze-builder"

KERNEL_VER="7.2.9"
KERNEL_TAR="linux-${KERNEL_VER}.tar.xz"
KERNEL_URL="https://cdn.kernel.org/pub/linux/kernel/v7.x/${KERNEL_TAR}"
JOBS="${JOBS:-$(nproc)}"

mkdir -p "${WORK_DIR}" "${SOURCES_DIR}" "${PKGS_DIR}"

# 1. Download kernel source
if [ ! -f "${SOURCES_DIR}/${KERNEL_TAR}" ]; then
    echo "[BUILD] Downloading ${KERNEL_TAR}..."
    curl -Lo "${SOURCES_DIR}/${KERNEL_TAR}" "${KERNEL_URL}"
fi

# 2. Extract
if [ ! -d "${WORK_DIR}/linux-${KERNEL_VER}" ]; then
    echo "[BUILD] Extracting ${KERNEL_TAR}..."
    tar -xf "${SOURCES_DIR}/${KERNEL_TAR}" -C "${WORK_DIR}"
fi

cd "${WORK_DIR}/linux-${KERNEL_VER}"

# 3. Configure kernel 7.2.9
echo "[BUILD] Configuring minimal linux-blaze kernel (${KERNEL_VER})..."
make x86_64_defconfig

# Built-in essential storage, EFI, virtio, ext4, systemd & display
./scripts/config --enable CONFIG_VIRTIO
./scripts/config --enable CONFIG_VIRTIO_PCI
./scripts/config --enable CONFIG_VIRTIO_BLK
./scripts/config --enable CONFIG_VIRTIO_NET
./scripts/config --enable CONFIG_VIRTIO_CONSOLE
./scripts/config --enable CONFIG_BLK_DEV_NVME
./scripts/config --enable CONFIG_ATA
./scripts/config --enable CONFIG_SATA_AHCI
./scripts/config --enable CONFIG_USB_STORAGE
./scripts/config --enable CONFIG_USB_XHCI_HCD
./scripts/config --enable CONFIG_EXT4_FS
./scripts/config --enable CONFIG_DEVTMPFS
./scripts/config --enable CONFIG_DEVTMPFS_MOUNT
./scripts/config --enable CONFIG_SERIAL_8250
./scripts/config --enable CONFIG_SERIAL_8250_CONSOLE
./scripts/config --enable CONFIG_EFI
./scripts/config --enable CONFIG_EFI_STUB
./scripts/config --enable CONFIG_EFIVAR_FS
./scripts/config --enable CONFIG_VT
./scripts/config --enable CONFIG_FRAMEBUFFER_CONSOLE
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
./scripts/config --enable CONFIG_NETFILTER
./scripts/config --enable CONFIG_NF_TABLES
./scripts/config --enable CONFIG_NF_TABLES_IPV4
./scripts/config --enable CONFIG_NF_TABLES_IPV6
./scripts/config --enable CONFIG_SECURITY
./scripts/config --enable CONFIG_SECURITYFS
./scripts/config --enable CONFIG_SECURITY_NETWORK
./scripts/config --enable CONFIG_SECURITY_APPARMOR
./scripts/config --enable CONFIG_SECURITY_LANDLOCK
./scripts/config --enable CONFIG_SECURITY_YAMA
./scripts/config --enable CONFIG_AUDIT
./scripts/config --enable CONFIG_AUDITSYSCALL
./scripts/config --enable CONFIG_FS_VERITY
./scripts/config --disable CONFIG_SECURITY_SELINUX
./scripts/config --set-str CONFIG_LSM "landlock,lockdown,yama,bpf,apparmor"
./scripts/config --enable CONFIG_DEFAULT_SECURITY_APPARMOR
./scripts/config --set-str CONFIG_DEFAULT_HOSTNAME "blaze"

# Modular driver stack for QEMU & hardware probing
./scripts/config --module CONFIG_DRM_VIRTIO_GPU
./scripts/config --module CONFIG_DRM_I915
./scripts/config --module CONFIG_DRM_AMDGPU
./scripts/config --module CONFIG_DRM_NOUVEAU
./scripts/config --module CONFIG_E1000E
./scripts/config --module CONFIG_IGC
./scripts/config --module CONFIG_R8169
./scripts/config --module CONFIG_IWLWIFI
./scripts/config --module CONFIG_DUMMY
./scripts/config --module CONFIG_BLK_DEV_LOOP

# Speed up compilation
./scripts/config --disable CONFIG_DEBUG_INFO
./scripts/config --disable CONFIG_DEBUG_INFO_BTF
./scripts/config --disable CONFIG_DEBUG_INFO_DWARF_TOOLCHAIN_DEFAULT

make olddefconfig

# 4. Compile bzImage and modules
echo "[BUILD] Compiling bzImage & modules for ${KERNEL_VER} (Jobs: ${JOBS})..."
make -j"${JOBS}" bzImage modules

# 5. Assemble package DESTDIR
KERNEL_DEST="${WORK_DIR}/kernel-dest"
rm -rf "${KERNEL_DEST}"
mkdir -p "${KERNEL_DEST}/boot" "${KERNEL_DEST}/usr/lib/modules"

cp arch/x86/boot/bzImage "${KERNEL_DEST}/boot/vmlinuz-blaze-7.2.9"
cp arch/x86/boot/bzImage "${KERNEL_DEST}/boot/vmlinuz-blaze"
chmod 0755 "${KERNEL_DEST}/boot/vmlinuz-blaze-7.2.9" "${KERNEL_DEST}/boot/vmlinuz-blaze"

# Install modules into DESTDIR
make modules_install INSTALL_MOD_PATH="${KERNEL_DEST}/usr"
if [ -d "${KERNEL_DEST}/usr/lib/modules" ]; then
    depmod -b "${KERNEL_DEST}/usr" "${KERNEL_VER}" || true
elif [ -d "${KERNEL_DEST}/lib/modules" ]; then
    mkdir -p "${KERNEL_DEST}/usr/lib"
    mv "${KERNEL_DEST}/lib/modules" "${KERNEL_DEST}/usr/lib/"
    rm -rf "${KERNEL_DEST}/lib"
    depmod -b "${KERNEL_DEST}/usr" "${KERNEL_VER}" || true
fi

# 6. Generate BERP Core initramfs (cpio.gz)
INITRAMFS_WORK="${WORK_DIR}/initramfs_work"
rm -rf "${INITRAMFS_WORK}"
mkdir -p "${INITRAMFS_WORK}"/{bin,sbin,dev,proc,sys,mnt,root,etc,run,usr/bin,usr/sbin}

cat << 'EOF_BERP' > "${INITRAMFS_WORK}/init.c"
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/reboot.h>
#include <fcntl.h>

static int check_cmdline_flag(const char *flag) {
    FILE *f = fopen("/proc/cmdline", "r");
    if (!f) return 0;
    char buf[1024] = {0};
    if (fgets(buf, sizeof(buf), f)) {
        if (strstr(buf, flag)) {
            fclose(f);
            return 1;
        }
    }
    fclose(f);
    return 0;
}

static void run_berp_recovery_console(const char *reason) {
    printf("\n==================================================================\n");
    printf("   Blaze Emergency Recovery Environment — BERP Core 1.0\n");
    printf("==================================================================\n");
    printf("[ WARN ] %s\n", reason);
    printf("Recovery environment active — read-only diagnostics console.\n\n");

    while (1) {
        printf("BERP Menu:\n");
        printf("  1) Show boot parameters & system info\n");
        printf("  2) Inspect block devices (/sys/class/block)\n");
        printf("  3) View dmesg kernel logs\n");
        printf("  4) Launch interactive emergency shell (/bin/sh)\n");
        printf("  5) Reboot system\n");
        printf("Select an option [1-5]: ");
        fflush(stdout);

        char input[32] = {0};
        if (!fgets(input, sizeof(input), stdin)) {
            printf("\n");
            continue;
        }

        int choice = atoi(input);
        if (choice == 1) {
            printf("\n--- Boot Cmdline ---\n");
            FILE *f = fopen("/proc/cmdline", "r");
            if (f) {
                char buf[512] = {0};
                if (fgets(buf, sizeof(buf), f)) printf("%s\n", buf);
                fclose(f);
            }
            printf("Kernel: Linux 7.2.9 (BlazeOS Native)\n\n");
        } else if (choice == 2) {
            printf("\n--- Detected Block Devices ---\n");
            system("ls -l /sys/class/block/ 2>/dev/null || true");
            printf("\n");
        } else if (choice == 3) {
            printf("\n--- Kernel Log Buffer (Tail) ---\n");
            system("dmesg | tail -n 25 2>/dev/null || true");
            printf("\n");
        } else if (choice == 4) {
            printf("\nStarting emergency shell. Type 'exit' to return to menu.\n");
            system("/bin/sh");
        } else if (choice == 5) {
            printf("\nRebooting system...\n");
            sync();
            reboot(RB_AUTOBOOT);
        } else {
            printf("Invalid selection.\n");
        }
    }
}

int main(int argc, char *argv[]) {
    (void)argc; (void)argv;
    printf("\n===============================================\n");
    printf("   BlazeOS Native — Early Boot Initramfs (7.2.9)\n");
    printf("===============================================\n\n");

    mount("proc", "/proc", "proc", 0, NULL);
    mount("sysfs", "/sys", "sysfs", 0, NULL);
    mount("devtmpfs", "/dev", "devtmpfs", 0, NULL);
    mount("tmpfs", "/run", "tmpfs", 0, NULL);

    if (check_cmdline_flag("berp") || check_cmdline_flag("rescue")) {
        run_berp_recovery_console("Emergency recovery explicitly requested via kernel command line ('berp').");
    }

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
        run_berp_recovery_console("Root block device not found after timeout (5.0s).");
    }

    printf("[INIT] Found root block device: %s\n", root_dev);
    printf("[INIT] Mounting %s to /mnt (ext4)...\n", root_dev);

    mkdir("/mnt", 0755);
    if (mount(root_dev, "/mnt", "ext4", MS_RELATIME, NULL) != 0) {
        run_berp_recovery_console("Failed to mount root filesystem on /mnt.");
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
    run_berp_recovery_console("Failed to execute /usr/lib/systemd/systemd on target rootfs.");
    return 1;
}
EOF_BERP

gcc -static -O2 "${INITRAMFS_WORK}/init.c" -o "${INITRAMFS_WORK}/init"
rm -f "${INITRAMFS_WORK}/init.c"
chmod 0755 "${INITRAMFS_WORK}/init"

# Copy minimal static busybox shell for BERP recovery console if available
if command -v busybox &>/dev/null; post_bb="$(which busybox)"; then
    cp "$post_bb" "${INITRAMFS_WORK}/bin/sh"
    chmod 0755 "${INITRAMFS_WORK}/bin/sh"
fi

# Package initramfs into CPIO.GZ
(cd "${INITRAMFS_WORK}" && find . -print0 | cpio --null -ov --format=newc | gzip -9 > "${KERNEL_DEST}/boot/initramfs-blaze.img")
cp "${KERNEL_DEST}/boot/initramfs-blaze.img" "${KERNEL_DEST}/boot/initramfs-blaze-7.2.9.img"

# 7. Create Recipe & Pack with blaze-builder
cat << 'EOF_RECIPE' > "${BLAZE_ROOT}/recipes/core/linux-blaze/recipe.toml"
[package]
name = "linux-blaze"
version = "7.2.9"
release = 1
architecture = "x86_64"
summary = "Vanilla Linux kernel 7.2.9 for BlazeOS Native"
license = "GPL-2.0-only"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://kernel.org"

[dependencies]
provides = ["kernel", "linux = 7.2.9"]

[build]
script = """
KERNEL_DEST_DIR="$(cd "$CURRENT_DIR" && while [ ! -d "build/kernel_7.2.9_work/kernel-dest" ] && [ "$PWD" != "/" ]; do cd ..; done && pwd)/build/kernel_7.2.9_work/kernel-dest"
cp -a "$KERNEL_DEST_DIR/"* "$DESTDIR/"
"""
EOF_RECIPE

"${BUILDER}" "${BLAZE_ROOT}/recipes/core/linux-blaze/recipe.toml"

echo "=== linux-blaze 7.2.9 Package Created Successfully ==="
ls -lh "${PKGS_DIR}/linux-blaze"*
