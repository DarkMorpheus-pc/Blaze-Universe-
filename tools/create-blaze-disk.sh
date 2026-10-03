#!/usr/bin/env bash
# ==============================================================================
# Blaze Universe — UEFI GPT Disk Image & Limine Bootloader Assembler
# ==============================================================================
# Creates:
#   build/blaze-disk.raw
# Layout:
#   GPT
#   ├── EFI System Partition (128 MB, FAT32) -> Limine BOOTX64.EFI + limine.conf
#   └── Blaze Root (1.9 GB, ext4, label=blaze-root) -> Full Portadora rootfs
# ==============================================================================

set -euo pipefail

BLAZE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DISK_IMG="${BLAZE_ROOT}/build/blaze-disk.raw"
BUILD_DIR="${BLAZE_ROOT}/build"
ROOTFS_DIR="${BUILD_DIR}/rootfs"

echo "=== Creating BlazeOS GPT Boot Disk Image ==="
echo "Target Disk: ${DISK_IMG}"

# 1. Create a 16GB raw disk image
rm -f "${DISK_IMG}"
truncate -s 16G "${DISK_IMG}"

# 2. Partition with sfdisk (GPT)
# Partition 1: ESP (128M), Partition 2: Root (Rest)
sfdisk "${DISK_IMG}" << 'EOF'
label: gpt
label-id: 88888888-8888-8888-8888-888888888888

start=2048, size=262144, type=c12a7328-f81f-11d2-ba4b-00a0c93ec93b, name="BLAZE-EFI", uuid=11111111-1111-1111-1111-111111111111
start=264192, size=33288192, type=4f68bce3-e8cd-4db1-96e7-fbcaf984b709, name="blaze-root", uuid=44444444-4444-4444-4444-444444444444
EOF

# Calculate partition byte offsets
ESP_START=$((2048 * 512))
ESP_SIZE=$((262144 * 512))
ROOT_START=$((264192 * 512))

# 3. Format ESP (FAT32)
ESP_IMG="${BUILD_DIR}/esp.img"
rm -f "${ESP_IMG}"
truncate -s "${ESP_SIZE}" "${ESP_IMG}"
mkfs.vfat -F32 -n "BLAZE-EFI" "${ESP_IMG}"

# Create EFI directory structure using mtools
mmd -i "${ESP_IMG}" ::EFI ::EFI/BOOT ::boot

# Copy Limine EFI binary
mcopy -i "${ESP_IMG}" /usr/share/limine/BOOTX64.EFI ::EFI/BOOT/BOOTX64.EFI

# Write limine.conf
cat << 'EOF' > "${BUILD_DIR}/limine.conf"
timeout: 3
default_entry: 2

/BlazeOS Native (systemd direct)
    protocol: linux
    kernel_path: boot():/boot/vmlinuz-linux
    cmdline: root=PARTUUID=44444444-4444-4444-4444-444444444444 rw console=ttyS0 console=tty0 init=/usr/lib/systemd/systemd

/BlazeOS Native (initramfs)
    protocol: linux
    kernel_path: boot():/boot/vmlinuz-linux
    module_path: boot():/boot/initramfs-linux.img
    cmdline: root=PARTUUID=44444444-4444-4444-4444-444444444444 rw console=ttyS0 console=tty0
EOF

mcopy -i "${ESP_IMG}" "${BUILD_DIR}/limine.conf" ::limine.conf
mcopy -i "${ESP_IMG}" "${BUILD_DIR}/limine.conf" ::EFI/BOOT/limine.conf

# Copy kernel to ESP as well (for guaranteed EFI loader access)
if [ -f "${ROOTFS_DIR}/boot/vmlinuz-linux" ]; then
    mcopy -i "${ESP_IMG}" "${ROOTFS_DIR}/boot/vmlinuz-linux" ::boot/vmlinuz-linux
fi
if [ -f "${ROOTFS_DIR}/boot/initramfs-linux.img" ]; then
    mcopy -i "${ESP_IMG}" "${ROOTFS_DIR}/boot/initramfs-linux.img" ::boot/initramfs-linux.img
fi

# 4. Format Root (ext4) and populate
ROOT_IMG="${BUILD_DIR}/root.img"
rm -f "${ROOT_IMG}"
# Size = 33288192 sectors * 512 bytes (exactly matches GPT partition size of 15.87 GiB)
ROOT_SIZE=$((33288192 * 512))
truncate -s "${ROOT_SIZE}" "${ROOT_IMG}"

# Format ext4 with label blaze-root
# unshare -r ensures all files in the ext4 rootfs are owned by UID 0 / GID 0 (root:root)!
unshare -r mkfs.ext4 -F -L "blaze-root" -d "${ROOTFS_DIR}" "${ROOT_IMG}"

# 5. Burn partitions into raw disk image
echo "Writing ESP partition into disk image..."
dd if="${ESP_IMG}" of="${DISK_IMG}" bs=1M seek=1 conv=notrunc status=none

echo "Writing Root partition into disk image..."
dd if="${ROOT_IMG}" of="${DISK_IMG}" bs=1M seek=129 conv=notrunc status=none

rm -f "${ESP_IMG}" "${ROOT_IMG}"

echo "=== Disk Image Created Successfully: ${DISK_IMG} ==="
ls -lh "${DISK_IMG}"
