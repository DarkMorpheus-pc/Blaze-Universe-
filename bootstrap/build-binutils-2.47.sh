#!/usr/bin/env bash
# ==============================================================================
# Blaze Universe — Upstream GNU Binutils 2.47 Builder
# ==============================================================================
set -euo pipefail

BLAZE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK_DIR="${BLAZE_ROOT}/build/binutils_2.47_work"
SOURCES_DIR="${BLAZE_ROOT}/build/sources"
PKGS_DIR="${BLAZE_ROOT}/build/packages"
BUILDER="${BLAZE_ROOT}/target/debug/blaze-builder"

BINUTILS_VER="2.47"
BINUTILS_TAR="binutils-${BINUTILS_VER}.tar.xz"
JOBS="${JOBS:-$(nproc)}"

mkdir -p "${WORK_DIR}" "${SOURCES_DIR}" "${PKGS_DIR}"

# 1. Extract
if [ ! -d "${WORK_DIR}/binutils-${BINUTILS_VER}" ]; then
    echo "Extracting ${BINUTILS_TAR}..."
    tar -xf "${SOURCES_DIR}/${BINUTILS_TAR}" -C "${WORK_DIR}"
fi

# 2. Check for versioned patches
PATCH_DIR="${BLAZE_ROOT}/recipes/core/binutils/patches"
if [ -d "${PATCH_DIR}" ]; then
    for p in "${PATCH_DIR}"/*.patch; do
        if [ -f "$p" ]; then
            echo "Applying patch: $p"
            patch -d "${WORK_DIR}/binutils-${BINUTILS_VER}" -Np1 -i "$p" || true
        fi
    done
fi

# 3. Configure and build binutils
BUILD_DIR="${WORK_DIR}/build"
mkdir -p "${BUILD_DIR}"
cd "${BUILD_DIR}"

if [ ! -f Makefile ]; then
    echo "Configuring binutils ${BINUTILS_VER}..."
    "${WORK_DIR}/binutils-${BINUTILS_VER}/configure" \
        --prefix=/usr \
        --sysconfdir=/etc \
        --localstatedir=/var \
        --enable-gold \
        --enable-ld=default \
        --enable-plugins \
        --enable-shared \
        --disable-werror \
        --enable-64-bit-bfd \
        --with-system-zlib \
        --enable-default-hash-style=gnu \
        --disable-nls
fi

echo "Compiling binutils ${BINUTILS_VER} (Jobs: ${JOBS})..."
make -j"${JOBS}" tooldir=/usr

# 4. Install into DESTDIR
DEST_DIR="${WORK_DIR}/dest"
rm -rf "${DEST_DIR}"
mkdir -p "${DEST_DIR}"
echo "Installing binutils into DESTDIR..."
make tooldir=/usr DESTDIR="${DEST_DIR}" install

# Clean up libtool archives (.la files) and info/man if desired
find "${DEST_DIR}" -name "*.la" -delete
rm -rf "${DEST_DIR}/usr/share/info"

cd "${BLAZE_ROOT}"

# 5. Package binutils 2.47
mkdir -p "${BLAZE_ROOT}/recipes/core/binutils"
cat << 'EOF_BINUTILS' > "${BLAZE_ROOT}/recipes/core/binutils/recipe.toml"
[package]
name = "binutils"
version = "2.47"
release = 1
architecture = "x86_64"
summary = "GNU Binutils (linker, assembler, and binary utilities)"
description = "GNU binary utilities for manipulating object code and binaries, including ld and as."
license = "GPL-3.0-or-later"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://www.gnu.org/software/binutils/"

[source]
url = "https://ftp.gnu.org/gnu/binutils/binutils-2.47.tar.xz"
sha256 = "154ab23b60070e8f27013c22977f1129425d67d1e8acd6e13010e617811e4cff"

[dependencies]
requires = ["glibc = 2.44"]
provides = [
    "binutils = 2.47",
    "cmd:ld",
    "cmd:as",
    "cmd:ar",
    "cmd:nm",
    "cmd:objcopy",
    "cmd:objdump",
    "cmd:ranlib",
    "cmd:readelf",
    "cmd:size",
    "cmd:strings",
    "cmd:strip"
]

[build]
script = """
cp -a "$CURRENT_DIR/build/binutils_2.47_work/dest/"* "$DESTDIR/"
"""
EOF_BINUTILS

"${BUILDER}" "${BLAZE_ROOT}/recipes/core/binutils/recipe.toml"

echo "=== Binutils 2.47 Package Created Successfully ==="
ls -lh "${PKGS_DIR}/binutils"*
