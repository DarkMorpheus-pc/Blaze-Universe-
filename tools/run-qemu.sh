#!/usr/bin/env bash
set -euo pipefail

BLAZE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DISK_IMG="${BLAZE_ROOT}/build/blaze-disk.raw"
OVMF_CODE="/usr/share/edk2/x64/OVMF.4m.fd"

if [ ! -f "${DISK_IMG}" ]; then
    echo "Error: Disk image not found at ${DISK_IMG}. Run tools/create-blaze-disk.sh first!"
    exit 1
fi

KVM_OPT=""
if [ -w /dev/kvm ]; then
    KVM_OPT="-enable-kvm -cpu host"
fi

echo "=== Launching BlazeOS Native in QEMU (UEFI) ==="
echo "Disk: ${DISK_IMG}"
echo "OVMF: ${OVMF_CODE}"
echo "KVM: ${KVM_OPT:-disabled}"
echo "To exit QEMU: Press Ctrl+A then X"
echo "-----------------------------------------------"

exec qemu-system-x86_64 \
    ${KVM_OPT} \
    -bios "${OVMF_CODE}" \
    -drive file="${DISK_IMG}",format=raw,if=virtio \
    -m 8G \
    -smp 8 \
    -nographic \
    -serial mon:stdio
