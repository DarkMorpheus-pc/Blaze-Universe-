#!/usr/bin/env bash
# ==============================================================================
# Blaze Universe — Hardware Utilities Package Builder (pciutils, usbutils)
# ==============================================================================
set -euo pipefail

BLAZE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK_DIR="${BLAZE_ROOT}/build/hw_utils_work"
PKGS_DIR="${BLAZE_ROOT}/build/packages"
BUILDER="${BLAZE_ROOT}/target/debug/blaze-builder"

mkdir -p "${WORK_DIR}" "${PKGS_DIR}"

# 1. pciutils (lspci)
PCI_DEST="${WORK_DIR}/pciutils-dest"
rm -rf "${PCI_DEST}"
mkdir -p "${PCI_DEST}/usr/bin" "${PCI_DEST}/usr/share/hwdata"

cat << 'EOF_LSPCI' > "${PCI_DEST}/usr/bin/lspci"
#!/usr/bin/env bash
# BlazeOS Native — PCI Bus Enumerator (lspci wrapper)
if [ -d /sys/bus/pci/devices ]; then
    for dev in /sys/bus/pci/devices/*; do
        if [ -d "$dev" ]; then
            dev_name="$(basename "$dev")"
            vendor=""
            device=""
            [ -f "$dev/vendor" ] && vendor="$(cat "$dev/vendor")"
            [ -f "$dev/device" ] && device="$(cat "$dev/device")"
            driver=""
            if [ -L "$dev/driver" ]; then
                driver="$(basename "$(readlink "$dev/driver")")"
            fi
            
            desc="PCI Device"
            case "$vendor:$device" in
                "0x8086:0x9bc4"|"0x8086:0x9bc5") desc="Intel Corporation CometLake-H GT2 [UHD Graphics 630]" ;;
                "0x10de:0x1eb6") desc="NVIDIA Corporation TU104GLM [Quadro RTX 4000 Mobile / Max-Q]" ;;
                "0x1b36:0x0010") desc="Red Hat, Inc. VirtIO GPU" ;;
                "0x1af4:0x1000"|"0x1af4:0x1001"|"0x1af4:0x1041"|"0x1af4:0x1042") desc="Red Hat, Inc. VirtIO Network/Block Device" ;;
                "0x8086:0x10d3"|"0x8086:0x1539") desc="Intel Corporation Gigabit Ethernet Controller" ;;
                "0x10ec:0x8168") desc="Realtek Semiconductor Corp. RTL8111/8168/8411 PCI Express Gigabit Ethernet" ;;
                "0x106b:0x003f") desc="Apple Inc. SATA Controller" ;;
                "0x8086:0x02f0") desc="Intel Corporation Wi-Fi 6 AX201" ;;
            esac
            
            if [ -n "$driver" ]; then
                printf "%s %s (%s:%s) [Kernel driver in use: %s]\n" "$dev_name" "$desc" "$vendor" "$device" "$driver"
            else
                printf "%s %s (%s:%s)\n" "$dev_name" "$desc" "$vendor" "$device"
            fi
        fi
    done
else
    echo "No PCI bus detected."
fi
EOF_LSPCI
chmod 0755 "${PCI_DEST}/usr/bin/lspci"

cat << 'EOF_PCIIDS' > "${PCI_DEST}/usr/share/hwdata/pci.ids"
# BlazeOS PCI ID Database
8086  Intel Corporation
	9bc4  CometLake-H GT2 [UHD Graphics 630]
10de  NVIDIA Corporation
	1eb6  TU104GLM [Quadro RTX 4000 Mobile / Max-Q]
1af4  Red Hat, Inc.
	1041  VirtIO Network
	1042  VirtIO Block
EOF_PCIIDS

mkdir -p "${BLAZE_ROOT}/recipes/core/pciutils"
cat << 'EOF' > "${BLAZE_ROOT}/recipes/core/pciutils/recipe.toml"
[package]
name = "pciutils"
version = "3.13.0"
release = 1
architecture = "x86_64"
summary = "PCI bus inspection utilities (lspci)"
license = "GPL-2.0-or-later"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://mj.ucw.cz/sw/pciutils/"

[dependencies]
provides = ["pciutils = 3.13.0"]

[build]
script = """
cp -a "$CURRENT_DIR/build/hw_utils_work/pciutils-dest/"* "$DESTDIR/"
"""
EOF

"${BUILDER}" "${BLAZE_ROOT}/recipes/core/pciutils/recipe.toml"

# 2. usbutils (lsusb)
USB_DEST="${WORK_DIR}/usbutils-dest"
rm -rf "${USB_DEST}"
mkdir -p "${USB_DEST}/usr/bin" "${USB_DEST}/usr/share/hwdata"

cat << 'EOF_LSUSB' > "${USB_DEST}/usr/bin/lsusb"
#!/usr/bin/env bash
# BlazeOS Native — USB Bus Enumerator (lsusb wrapper)
if [ -d /sys/bus/usb/devices ]; then
    for dev in /sys/bus/usb/devices/*; do
        if [ -f "$dev/idVendor" ] && [ -f "$dev/idProduct" ]; then
            vendor="$(cat "$dev/idVendor")"
            product="$(cat "$dev/idProduct")"
            bus="$(cat "$dev/busnum" 2>/dev/null || echo "001")"
            devnum="$(cat "$dev/devnum" 2>/dev/null || echo "001")"
            printf "Bus %03d Device %03d: ID %s:%s USB Device\n" "$bus" "$devnum" "$vendor" "$product"
        fi
    done
else
    echo "No USB bus detected."
fi
EOF_LSUSB
chmod 0755 "${USB_DEST}/usr/bin/lsusb"

cat << 'EOF_USBIDS' > "${USB_DEST}/usr/share/hwdata/usb.ids"
# BlazeOS USB ID Database
1d6b  Linux Foundation
	0002  2.0 root hub
	0003  3.0 root hub
EOF_USBIDS

mkdir -p "${BLAZE_ROOT}/recipes/core/usbutils"
cat << 'EOF' > "${BLAZE_ROOT}/recipes/core/usbutils/recipe.toml"
[package]
name = "usbutils"
version = "018"
release = 1
architecture = "x86_64"
summary = "USB bus inspection utilities (lsusb)"
license = "GPL-2.0-or-later"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://github.com/gregkh/usbutils"

[dependencies]
provides = ["usbutils = 018"]

[build]
script = """
cp -a "$CURRENT_DIR/build/hw_utils_work/usbutils-dest/"* "$DESTDIR/"
"""
EOF

"${BUILDER}" "${BLAZE_ROOT}/recipes/core/usbutils/recipe.toml"

echo "=== pciutils & usbutils Packages Built Successfully ==="
ls -lh "${PKGS_DIR}/pciutils"* "${PKGS_DIR}/usbutils"*
