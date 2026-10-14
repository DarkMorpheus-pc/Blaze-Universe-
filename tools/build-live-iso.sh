#!/usr/bin/env bash
# BlazeOS Native — Milestone 10 Phase A reproducible Live ISO builder
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BLAZE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ROOTFS="${BLAZE_ROOT}/build/rootfs-b11"
KERNEL_DEST="${BLAZE_ROOT}/build/kernel_7.2.9_work/kernel-dest"
STAGING="${BLAZE_ROOT}/build/live-iso-staging"
OUTPUT_DIR="${BLAZE_ROOT}/build/iso"
OUTPUT_ISO="${OUTPUT_DIR}/BlazeOS-Native-m10-phase-c2-x86_64.iso"
LIMINE_DIR="$("${SCRIPT_DIR}/prepare-limine.sh" | tail -n1)"
LIMINE_TOOL="${LIMINE_DIR}/limine"
LIMINE_DATA="${LIMINE_DIR}"

KERNEL="${KERNEL_DEST}/boot/vmlinuz-blaze-7.2.9"
INITRAMFS="${KERNEL_DEST}/boot/initramfs-blaze-7.2.9.img"

for tool in mksquashfs xorriso cargo mkfs.vfat mkfs.ext4 unsquashfs; do
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
mkdir -p "${STAGING}/boot" "${STAGING}/EFI/BOOT" "${STAGING}/blaze" "${STAGING}/installer" \
         "${STAGING}/.disk" "${OUTPUT_DIR}"

cp "${KERNEL}" "${STAGING}/boot/vmlinuz-blaze-7.2.9"
cp "${INITRAMFS}" "${STAGING}/boot/initramfs-blaze-7.2.9.img"
cp "${LIMINE_DATA}/limine-bios-cd.bin" "${STAGING}/boot/"
cp "${LIMINE_DATA}/limine-bios.sys" "${STAGING}/boot/"
cp "${LIMINE_DATA}/limine-uefi-cd.bin" "${STAGING}/boot/"
cp "${LIMINE_DATA}/BOOTX64.EFI" "${STAGING}/EFI/BOOT/BOOTX64.EFI"
cp "${LIMINE_DATA}/BOOTX64.EFI" "${STAGING}/installer/BOOTX64.EFI"
cp "${LIMINE_DATA}/limine-bios.sys" "${STAGING}/installer/limine-bios.sys"
cp "${LIMINE_TOOL}" "${STAGING}/installer/limine"

echo "[LIVE-ISO] Building and staging the Solar Installer engine..."
cargo build --release --manifest-path "${BLAZE_ROOT}/Cargo.toml" -p solar-installer
cargo build --release --manifest-path "${BLAZE_ROOT}/Cargo.toml" -p portadora
install -Dm755 "${BLAZE_ROOT}/target/release/solar-installer" \
    "${ROOTFS}/usr/bin/solar-installer"
install -Dm755 "${BLAZE_ROOT}/target/release/portadora" \
    "${ROOTFS}/usr/bin/portadora"
install -Dm644 "${BLAZE_ROOT}/build/repository/stable/metadata/root.json" \
    "${ROOTFS}/etc/portadora/trusted/root.json"
install -Dm755 "${BLAZE_ROOT}/config/solar-installer/solar-installer-gui" \
    "${ROOTFS}/usr/bin/solar-installer-gui"
install -Dm644 "${BLAZE_ROOT}/config/solar-installer/solar-installer.desktop" \
    "${ROOTFS}/usr/share/applications/solar-installer.desktop"
install -d "${ROOTFS}/usr/share/solar-installer"
install -Dm644 "${BLAZE_ROOT}/config/solar-installer/"*.qml \
    "${ROOTFS}/usr/share/solar-installer/"
install -d -m0750 "${ROOTFS}/etc/sudoers.d"
if [[ -e "${ROOTFS}/etc/sudoers.d/solar-installer-live" ]]; then
    chmod u+w "${ROOTFS}/etc/sudoers.d/solar-installer-live"
fi
cat > "${ROOTFS}/etc/sudoers.d/solar-installer-live" <<'EOF'
# Live-media only: removed from the target immediately after extraction.
blaze ALL=(root) NOPASSWD: /usr/bin/solar-installer
EOF
chmod 0440 "${ROOTFS}/etc/sudoers.d/solar-installer-live"
install -Dm644 "${BLAZE_ROOT}/config/blaze-bash-profile" \
    "${ROOTFS}/home/blaze/.bash_profile"
chown 1000:1000 "${ROOTFS}/home/blaze/.bash_profile" 2>/dev/null || true
install -Dm644 "${BLAZE_ROOT}/config/getty-tty1-autologin.conf" \
    "${ROOTFS}/etc/systemd/system/getty@tty1.service.d/autologin.conf"
install -Dm644 "${BLAZE_ROOT}/config/virtio-gpu.conf" \
    "${ROOTFS}/etc/modules-load.d/virtio-gpu.conf"

# Bundle the deployment tools and their resolved runtime libraries. Retaining
# them in the installed root also supports later recovery and repair workflows.
for live_tool in mkfs.vfat mkfs.ext4 unsquashfs; do
    tool_path="$(command -v "${live_tool}")"
    install -Dm755 "${tool_path}" "${ROOTFS}${tool_path}"
    while read -r library; do
        [[ -n "${library}" && -f "${library}" ]] || continue
        install -Dm755 "${library}" "${ROOTFS}${library}"
    done < <(ldd "${tool_path}" | awk '/=> \// {print $3} /^\// {print $1}')
done

cat > "${STAGING}/limine.conf" <<'EOF'
timeout: 3
default_entry: 1

/BlazeOS Native Live (Linux 7.2.9)
    protocol: linux
    kernel_path: boot():/boot/vmlinuz-blaze-7.2.9
    module_path: boot():/boot/initramfs-blaze-7.2.9.img
    cmdline: blaze.live=1 systemd.gpt_auto=0 ro console=ttyS0 console=tty0 quiet loglevel=3

/Blaze Emergency Recovery Environment
    protocol: linux
    kernel_path: boot():/boot/vmlinuz-blaze-7.2.9
    module_path: boot():/boot/initramfs-blaze-7.2.9.img
    cmdline: blaze.live=1 systemd.gpt_auto=0 ro console=ttyS0 console=tty0 berp
EOF
cp "${STAGING}/limine.conf" "${STAGING}/EFI/BOOT/limine.conf"

echo "BlazeOS Native Milestone 10 Phase C.2" > "${STAGING}/.disk/info"

echo "[LIVE-ISO] Synchronizing kernel modules with the live kernel..."
rm -rf "${ROOTFS}/usr/lib/modules/7.2.9"
mkdir -p "${ROOTFS}/usr/lib/modules"
cp -a "${KERNEL_DEST}/usr/lib/modules/7.2.9" "${ROOTFS}/usr/lib/modules/7.2.9"

echo "[LIVE-ISO] Compressing immutable root filesystem..."
mksquashfs "${ROOTFS}" "${STAGING}/blaze/rootfs.squashfs" \
    -noappend -comp gzip -b 1M -all-root -wildcards \
    -e 'boot/*' 'dev/*' 'proc/*' 'run/*' 'sys/*' 'tmp/*' 'etc/fstab'

(
    cd "${STAGING}"
    find blaze boot installer -type f -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS
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
