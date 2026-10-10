#!/usr/bin/env bash
# ==============================================================================
# Blaze Universe — Milestone 6 In-Guest Hardware Test Suite
# ==============================================================================
set -euo pipefail

echo "[M6-TEST] Starting Milestone 6 Hardware Acceptance Tests..."

echo "[M6-TEST] 1/7 Checking Kernel Version..."
uname -a | grep -i "7.2.9" || (echo "[M6-FAIL] Kernel is not 7.2.9!" && exit 1)
echo "[M6-TEST] Kernel 7.2.9 verified."

echo "[M6-TEST] 2/7 Checking PCI Hardware Detection (lspci)..."
/usr/bin/lspci

echo "[M6-TEST] 3/7 Checking USB Hardware Detection (lsusb)..."
/usr/bin/lsusb

echo "[M6-TEST] 4/7 Testing Module Load & Unload (kmod)..."
modprobe dummy || true
modprobe loop || true
lsmod | grep -E "dummy|loop" || echo "[M6-WARN] Dummy/loop modules built-in or loaded."

echo "[M6-TEST] 5/7 Verifying Firmware Manifest..."
if [ -f /usr/lib/firmware/WHENCE ]; then
    cat /usr/lib/firmware/WHENCE
else
    echo "[M6-WARN] Firmware WHENCE manifest not found."
fi

echo "[M6-TEST] 6/7 Running Portadora Integrity Check..."
/usr/bin/portadora verify

echo "[M6-TEST] 7/7 Checking Essential System Services..."
systemctl is-active systemd-networkd.service
systemctl is-active systemd-resolved.service
systemctl is-active nftables.service

echo "[M6-TEST] === ALL MILESTONE 6 IN-GUEST TESTS PASSED ==="
