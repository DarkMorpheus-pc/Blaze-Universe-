#!/usr/bin/env bash
# BlazeOS Native — Milestone 10 Phase A reproducible Live ISO builder
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BLAZE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ROOTFS="${BLAZE_ROOT}/build/rootfs-b11"
KERNEL_DEST="${BLAZE_ROOT}/build/kernel_7.2.9_work/kernel-dest"
STAGING="${BLAZE_ROOT}/build/live-iso-staging"
OUTPUT_DIR="${BLAZE_ROOT}/build/iso"
OUTPUT_ISO="${OUTPUT_DIR}/BlazeOS-Native-m10-phase-a-x86_64.iso"
LIMINE_DIR="$("${SCRIPT_DIR}/prepare-limine.sh" | tail -n1)"
LIMINE_TOOL="${LIMINE_DIR}/limine"
LIMINE_DATA="${LIMINE_DIR}"

KERNEL="${KERNEL_DEST}/boot/vmlinuz-blaze-7.2.9"
INITRAMFS="${KERNEL_DEST}/boot/initramfs-blaze-7.2.9.img"

for tool in mksquashfs xorriso; do
    command -v "${tool}" >/dev/null || {
        echo "[ERROR] Required host tool is missing: ${tool}" >&2
        exit 1
    }
done

for artifact in "${KERNEL}" "${INITRAMFS}" "${LIMINE_DATA}/limine-bios-cd.bin" \
                "${LIMINE_DATA}/limine-bios.sys" "${LIMINE_DATA}/limine-uefi-cd.bin"; do
    [[ -f "${artifact}" ]] || {
        echo "[ERROR] Required artifact is missing: ${artifact}" >&2
        exit 1
    }
done

echo "[LIVE-ISO] Preparing staging tree..."
rm -rf "${STAGING}"
mkdir -p "${STAGING}/boot" "${STAGING}/EFI/BOOT" "${STAGING}/blaze" \
         "${STAGING}/.disk" "${OUTPUT_DIR}"

cp "${KERNEL}" "${STAGING}/boot/vmlinuz-blaze-7.2.9"
cp "${INITRAMFS}" "${STAGING}/boot/initramfs-blaze-7.2.9.img"
cp "${LIMINE_DATA}/limine-bios-cd.bin" "${STAGING}/boot/"
cp "${LIMINE_DATA}/limine-bios.sys" "${STAGING}/boot/"
cp "${LIMINE_DATA}/limine-uefi-cd.bin" "${STAGING}/boot/"
cp "${LIMINE_DATA}/BOOTX64.EFI" "${STAGING}/EFI/BOOT/BOOTX64.EFI"

cat > "${STAGING}/limine.conf" <<'EOF'
timeout: 3
default_entry: 1

/BlazeOS Native Live (Linux 7.2.9)
    protocol: linux
    kernel_path: boot():/boot/vmlinuz-blaze-7.2.9
    module_path: boot():/boot/initramfs-blaze-7.2.9.img
    cmdline: blaze.live=1 ro console=ttyS0 console=tty0 quiet loglevel=3

/Blaze Emergency Recovery Environment
    protocol: linux
    kernel_path: boot():/boot/vmlinuz-blaze-7.2.9
    module_path: boot():/boot/initramfs-blaze-7.2.9.img
    cmdline: blaze.live=1 ro console=ttyS0 console=tty0 berp
EOF
cp "${STAGING}/limine.conf" "${STAGING}/EFI/BOOT/limine.conf"

echo "BlazeOS Native Milestone 10 Phase A" > "${STAGING}/.disk/info"

echo "[LIVE-ISO] Synchronizing kernel modules with the live kernel..."
rm -rf "${ROOTFS}/usr/lib/modules/7.2.9"
mkdir -p "${ROOTFS}/usr/lib/modules"
cp -a "${KERNEL_DEST}/usr/lib/modules/7.2.9" "${ROOTFS}/usr/lib/modules/7.2.9"

echo "[LIVE-ISO] Compressing immutable root filesystem..."
mksquashfs "${ROOTFS}" "${STAGING}/blaze/rootfs.squashfs" \
    -noappend -comp gzip -b 1M -all-root -wildcards \
    -e 'boot/*' 'dev/*' 'proc/*' 'run/*' 'sys/*' 'tmp/*'

(
    cd "${STAGING}"
    find blaze boot -type f -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS
)

echo "[LIVE-ISO] Creating hybrid BIOS/UEFI ISO..."
xorriso -as mkisofs \
    -R -r -J -joliet-long \
    -V "BLAZEOS_LIVE" \
    -b boot/limine-bios-cd.bin \
    -no-emul-boot -boot-load-size 4 -boot-info-table \
    --efi-boot boot/limine-uefi-cd.bin \
    -efi-boot-part --efi-boot-image --protective-msdos-label \
    "${STAGING}" -o "${OUTPUT_ISO}"

"${LIMINE_TOOL}" bios-install "${OUTPUT_ISO}"
sha256sum "${OUTPUT_ISO}" > "${OUTPUT_ISO}.sha256"

echo "[LIVE-ISO] Created: ${OUTPUT_ISO}"
du -h "${OUTPUT_ISO}" "${STAGING}/blaze/rootfs.squashfs"
