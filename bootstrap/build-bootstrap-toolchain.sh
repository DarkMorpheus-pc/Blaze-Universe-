#!/usr/bin/env bash
# ==============================================================================
# Blaze Universe — Automated Cross-Bootstrap Toolchain Pipeline
# ==============================================================================
# Pipeline:
#   1. Linux API Headers (6.8+)
#   2. Binutils (Target: x86_64-blaze-linux-gnu)
#   3. GCC Stage 1 (Static C Compiler)
#   4. Glibc (C Library + Dynamic Linker)
#   5. Libstdc++ & GCC Final
# ==============================================================================

set -euo pipefail

BLAZE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="${BLAZE_ROOT}/build/bootstrap"
TOOLS_DIR="${BUILD_DIR}/tools"
SYSROOT_DIR="${BUILD_DIR}/sysroot"
SOURCES_DIR="${BLAZE_ROOT}/build/sources"
TARGET="x86_64-blaze-linux-gnu"
JOBS="${JOBS:-$(nproc)}"

export PATH="${TOOLS_DIR}/bin:${PATH}"

echo "=== BlazeOS Bootstrap Toolchain ==="
echo "Root:    ${BLAZE_ROOT}"
echo "Target:  ${TARGET}"
echo "Tools:   ${TOOLS_DIR}"
echo "Sysroot: ${SYSROOT_DIR}"
echo "Jobs:    ${JOBS}"

mkdir -p "${BUILD_DIR}" "${TOOLS_DIR}" "${SYSROOT_DIR}" "${SOURCES_DIR}"

# 1. Linux API Headers
echo "--- [1/5] Installing Linux API Headers ---"
LINUX_VER="6.8.9"
LINUX_TAR="linux-${LINUX_VER}.tar.xz"
if [ ! -f "${SOURCES_DIR}/${LINUX_TAR}" ]; then
    echo "Downloading ${LINUX_TAR}..."
    curl -Lo "${SOURCES_DIR}/${LINUX_TAR}" "https://cdn.kernel.org/pub/linux/kernel/v6.x/${LINUX_TAR}"
fi

tar -xf "${SOURCES_DIR}/${LINUX_TAR}" -C "${BUILD_DIR}"
cd "${BUILD_DIR}/linux-${LINUX_VER}"
make mrproper
make ARCH=x86_64 INSTALL_HDR_PATH="${SYSROOT_DIR}/usr" headers_install
cd "${BLAZE_ROOT}"

# 2. Cross-Binutils
echo "--- [2/5] Building Cross-Binutils ---"
BINUTILS_VER="2.42"
BINUTILS_TAR="binutils-${BINUTILS_VER}.tar.xz"
if [ ! -f "${SOURCES_DIR}/${BINUTILS_TAR}" ]; then
    echo "Downloading ${BINUTILS_TAR}..."
    curl -Lo "${SOURCES_DIR}/${BINUTILS_TAR}" "https://ftp.gnu.org/gnu/binutils/${BINUTILS_TAR}"
fi

tar -xf "${SOURCES_DIR}/${BINUTILS_TAR}" -C "${BUILD_DIR}"
mkdir -p "${BUILD_DIR}/binutils-build"
cd "${BUILD_DIR}/binutils-build"
"${BUILD_DIR}/binutils-${BINUTILS_VER}/configure" \
    --target="${TARGET}" \
    --prefix="${TOOLS_DIR}" \
    --with-sysroot="${SYSROOT_DIR}" \
    --disable-nls \
    --disable-werror
make -j"${JOBS}"
make install
cd "${BLAZE_ROOT}"

echo "=== Cross-Binutils Installed Successfully ==="
