#!/usr/bin/env bash
# ==============================================================================
# BlazeOS Native — Interactive QEMU Boot Script
# Boots BlazeOS Native GPT raw disk with UEFI (OVMF), VirtIO-GPU, 4 vCPUs, 2GB RAM
# Uses a safe, disposable QCOW2 overlay so the base disk is never damaged.
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BLAZE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BASE_DISK="${BLAZE_ROOT}/build/blaze-disk-b11.raw"
OVERLAY_DISK="/tmp/blaze-native-manual-overlay.qcow2"
OVMF_CODE="/usr/share/edk2/x64/OVMF.4m.fd"
KERNEL="${BLAZE_ROOT}/build/rootfs-b11/boot/vmlinuz-blaze-7.2.9"
INITRD="${BLAZE_ROOT}/build/rootfs-b11/boot/initramfs-blaze-7.2.9.img"

echo "=================================================================="
echo "         BlazeOS Native Interactive Virtual Machine               "
echo "=================================================================="

if [[ ! -f "$BASE_DISK" ]]; then
    echo "[HATA] Disk imajı bulunamadı: $BASE_DISK"
    exit 1
fi

if [[ ! -f "$OVMF_CODE" ]]; then
    echo "[HATA] OVMF UEFI bellenimi bulunamadı: $OVMF_CODE"
    exit 1
fi

# Clean previous overlay
rm -f "$OVERLAY_DISK"

echo "[BİLGİ] Orijinal diski korumak için geçici QCOW2 overlay oluşturuluyor..."
qemu-img create -f qcow2 -b "$BASE_DISK" -F raw "$OVERLAY_DISK" > /dev/null

echo "[BİLGİ] Sanal makine başlatılıyor..."
echo "  - CPU / Bellek: 4 Çekirdek / 2048 MB RAM"
echo "  - Grafik: VirtIO-GPU (1280x800)"
echo "  - Giriş: Fare ve Klavye"
echo "  - Çıkış için pencereyi kapatabilir veya terminalde Ctrl+C yapabilirsiniz."
echo "------------------------------------------------------------------"

QEMU_ACCEL=()
if [[ -e /dev/kvm ]] && [[ -r /dev/kvm ]] && [[ -w /dev/kvm ]]; then
    QEMU_ACCEL=("-enable-kvm" "-cpu" "host")
else
    QEMU_ACCEL=("-cpu" "qemu64")
fi

exec qemu-system-x86_64 \
    "${QEMU_ACCEL[@]}" \
    -bios "$OVMF_CODE" \
    -m 2048 \
    -smp 4 \
    -vga virtio \
    -display gtk,gl=on \
    -drive "file=${OVERLAY_DISK},format=qcow2,if=virtio,id=drv0" \
    -device intel-hda \
    -device hda-duplex \
    -kernel "$KERNEL" \
    -initrd "$INITRD" \
    -append "root=PARTUUID=44444444-4444-4444-4444-444444444444 rw console=tty0 quiet loglevel=3" \
    -net none
