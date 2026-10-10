#!/usr/bin/env bash
# ==============================================================================
# Blaze Universe — Split Linux Firmware Package Builder (Tag 20260916)
# ==============================================================================
set -euo pipefail

BLAZE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK_DIR="${BLAZE_ROOT}/build/firmware_work"
PKGS_DIR="${BLAZE_ROOT}/build/packages"
BUILDER="${BLAZE_ROOT}/target/debug/blaze-builder"

mkdir -p "${WORK_DIR}" "${PKGS_DIR}"

# 1. Prepare Base Firmware Directory
FW_BASE="${WORK_DIR}/firmware-base-dest"
rm -rf "${FW_BASE}"
mkdir -p "${FW_BASE}/usr/lib/firmware"/{intel-ucode,amd-ucode}

cat << 'EOF' > "${FW_BASE}/usr/lib/firmware/WHENCE"
BlazeOS Native Firmware Manifest (20260916 Snapshot)
Licenses: GPL, BSD, Proprietary Redistributable per vendor specs.
EOF

cat << 'EOF' > "${FW_BASE}/usr/lib/firmware/regulatory.db"
BLAZE_WIRELESS_REGULATORY_DATABASE_PLACEHOLDER
EOF

touch "${FW_BASE}/usr/lib/firmware/regulatory.db.p7s"
touch "${FW_BASE}/usr/lib/firmware/intel-ucode/06-8e-0c"
touch "${FW_BASE}/usr/lib/firmware/amd-ucode/microcode_amd.bin"

mkdir -p "${BLAZE_ROOT}/recipes/core/linux-firmware-base"
cat << 'EOF' > "${BLAZE_ROOT}/recipes/core/linux-firmware-base/recipe.toml"
[package]
name = "linux-firmware-base"
version = "20260916"
release = 1
architecture = "x86_64"
summary = "Core Linux firmware, CPU microcode, and wireless regulatory DB"
license = "GPL-2.0-only AND Custom-redistributable"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://git.kernel.org/pub/scm/linux/kernel/git/firmware/linux-firmware.git"

[dependencies]
provides = ["firmware-base = 20260916"]

[build]
script = """
cp -a "$CURRENT_DIR/build/firmware_work/firmware-base-dest/"* "$DESTDIR/"
"""
EOF

"${BUILDER}" "${BLAZE_ROOT}/recipes/core/linux-firmware-base/recipe.toml"

# 2. Prepare Intel Firmware Directory
FW_INTEL="${WORK_DIR}/firmware-intel-dest"
rm -rf "${FW_INTEL}"
mkdir -p "${FW_INTEL}/usr/lib/firmware"/{i915,xe,intel}

touch "${FW_INTEL}/usr/lib/firmware/i915/kbl_guc_33.0.0.bin"
touch "${FW_INTEL}/usr/lib/firmware/i915/kbl_huc_4.0.0.bin"
touch "${FW_INTEL}/usr/lib/firmware/i915/kbl_dmc_ver1_04.bin"
touch "${FW_INTEL}/usr/lib/firmware/xe/tgl_guc_70.1.1.bin"
touch "${FW_INTEL}/usr/lib/firmware/iwlwifi-cc-a0-63.ucode"

mkdir -p "${BLAZE_ROOT}/recipes/core/linux-firmware-intel"
cat << 'EOF' > "${BLAZE_ROOT}/recipes/core/linux-firmware-intel/recipe.toml"
[package]
name = "linux-firmware-intel"
version = "20260916"
release = 1
architecture = "x86_64"
summary = "Intel GPU (i915/xe) and Wi-Fi firmware binaries"
license = "Custom-Intel-Redistributable"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://git.kernel.org/pub/scm/linux/kernel/git/firmware/linux-firmware.git"

[dependencies]
provides = ["firmware-intel = 20260916"]

[build]
script = """
cp -a "$CURRENT_DIR/build/firmware_work/firmware-intel-dest/"* "$DESTDIR/"
"""
EOF

"${BUILDER}" "${BLAZE_ROOT}/recipes/core/linux-firmware-intel/recipe.toml"

# 3. Prepare AMD Firmware Directory
FW_AMD="${WORK_DIR}/firmware-amd-dest"
rm -rf "${FW_AMD}"
mkdir -p "${FW_AMD}/usr/lib/firmware/amdgpu"

touch "${FW_AMD}/usr/lib/firmware/amdgpu/navi10_gpu_info.bin"

mkdir -p "${BLAZE_ROOT}/recipes/core/linux-firmware-amdgpu"
cat << 'EOF' > "${BLAZE_ROOT}/recipes/core/linux-firmware-amdgpu/recipe.toml"
[package]
name = "linux-firmware-amdgpu"
version = "20260916"
release = 1
architecture = "x86_64"
summary = "AMD Radeon GPU firmware binaries"
license = "Custom-AMD-Redistributable"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://git.kernel.org/pub/scm/linux/kernel/git/firmware/linux-firmware.git"

[dependencies]
provides = ["firmware-amdgpu = 20260916"]

[build]
script = """
cp -a "$CURRENT_DIR/build/firmware_work/firmware-amd-dest/"* "$DESTDIR/"
"""
EOF

"${BUILDER}" "${BLAZE_ROOT}/recipes/core/linux-firmware-amdgpu/recipe.toml"

# 4. Prepare NVIDIA Firmware Directory (Nouveau open-source firmware)
FW_NVIDIA="${WORK_DIR}/firmware-nvidia-dest"
rm -rf "${FW_NVIDIA}"
mkdir -p "${FW_NVIDIA}/usr/lib/firmware/nvidia/tu104"

touch "${FW_NVIDIA}/usr/lib/firmware/nvidia/tu104/gsp.bin"

mkdir -p "${BLAZE_ROOT}/recipes/core/linux-firmware-nvidia"
cat << 'EOF' > "${BLAZE_ROOT}/recipes/core/linux-firmware-nvidia/recipe.toml"
[package]
name = "linux-firmware-nvidia"
version = "20260916"
release = 1
architecture = "x86_64"
summary = "NVIDIA Nouveau GPU firmware binaries"
license = "Custom-NVIDIA-Redistributable"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://git.kernel.org/pub/scm/linux/kernel/git/firmware/linux-firmware.git"

[dependencies]
provides = ["firmware-nvidia = 20260916"]

[build]
script = """
cp -a "$CURRENT_DIR/build/firmware_work/firmware-nvidia-dest/"* "$DESTDIR/"
"""
EOF

"${BUILDER}" "${BLAZE_ROOT}/recipes/core/linux-firmware-nvidia/recipe.toml"

# 5. Prepare Network Firmware Directory
FW_NET="${WORK_DIR}/firmware-network-dest"
rm -rf "${FW_NET}"
mkdir -p "${FW_NET}/usr/lib/firmware"/{rtl_nic,rtlwifi}

touch "${FW_NET}/usr/lib/firmware/rtl_nic/rtl8168h-2.fw"
touch "${FW_NET}/usr/lib/firmware/rtlwifi/rtl8192cfw.bin"

mkdir -p "${BLAZE_ROOT}/recipes/core/linux-firmware-network"
cat << 'EOF' > "${BLAZE_ROOT}/recipes/core/linux-firmware-network/recipe.toml"
[package]
name = "linux-firmware-network"
version = "20260916"
release = 1
architecture = "x86_64"
summary = "Realtek and network card firmware binaries"
license = "Custom-Redistributable"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://git.kernel.org/pub/scm/linux/kernel/git/firmware/linux-firmware.git"

[dependencies]
provides = ["firmware-network = 20260916"]

[build]
script = """
cp -a "$CURRENT_DIR/build/firmware_work/firmware-network-dest/"* "$DESTDIR/"
"""
EOF

"${BUILDER}" "${BLAZE_ROOT}/recipes/core/linux-firmware-network/recipe.toml"

echo "=== All 5 Split Firmware Packages Built Successfully ==="
ls -lh "${PKGS_DIR}/linux-firmware"*
