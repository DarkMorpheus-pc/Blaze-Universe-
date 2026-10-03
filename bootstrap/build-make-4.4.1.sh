#!/usr/bin/env bash
# ==============================================================================
# Blaze Universe — Upstream GNU Make 4.4.1 Builder
# ==============================================================================
set -euo pipefail

BLAZE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK_DIR="${BLAZE_ROOT}/build/make_4.4.1_work"
SOURCES_DIR="${BLAZE_ROOT}/build/sources"
PKGS_DIR="${BLAZE_ROOT}/build/packages"
BUILDER="${BLAZE_ROOT}/target/debug/blaze-builder"

MAKE_VER="4.4.1"
MAKE_TAR="make-${MAKE_VER}.tar.gz"
JOBS="${JOBS:-$(nproc)}"

mkdir -p "${WORK_DIR}" "${SOURCES_DIR}" "${PKGS_DIR}"

# 1. Extract
if [ ! -d "${WORK_DIR}/make-${MAKE_VER}" ]; then
    echo "Extracting ${MAKE_TAR}..."
    tar -xf "${SOURCES_DIR}/${MAKE_TAR}" -C "${WORK_DIR}"
fi

# 2. Configure and build make
BUILD_DIR="${WORK_DIR}/build"
mkdir -p "${BUILD_DIR}"
cd "${BUILD_DIR}"

if [ ! -f Makefile ]; then
    echo "Configuring make ${MAKE_VER}..."
    "${WORK_DIR}/make-${MAKE_VER}/configure" \
        --prefix=/usr \
        --without-guile \
        --disable-nls
fi

echo "Compiling make ${MAKE_VER} (Jobs: ${JOBS})..."
make -j"${JOBS}"

# 3. Install into DESTDIR
DEST_DIR="${WORK_DIR}/dest"
rm -rf "${DEST_DIR}"
mkdir -p "${DEST_DIR}"
echo "Installing make into DESTDIR..."
make DESTDIR="${DEST_DIR}" install

# Clean up info/man if desired
rm -rf "${DEST_DIR}/usr/share/info"

cd "${BLAZE_ROOT}"

# 4. Package make 4.4.1
mkdir -p "${BLAZE_ROOT}/recipes/core/make"
cat << 'EOF_MAKE' > "${BLAZE_ROOT}/recipes/core/make/recipe.toml"
[package]
name = "make"
version = "4.4.1"
release = 1
architecture = "x86_64"
summary = "GNU Make utility to maintain groups of programs"
description = "GNU Make controls the generation of executables and other non-source files of a program."
license = "GPL-3.0-or-later"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://www.gnu.org/software/make/"

[source]
url = "https://ftp.gnu.org/gnu/make/make-4.4.1.tar.gz"
sha256 = "dd16fb1d67bfab79a72f5e8390735c49e3e8e70b4945a15ab1f81ddb78658fb3"

[dependencies]
requires = ["glibc = 2.44"]
provides = [
    "make = 4.4.1",
    "cmd:make"
]

[build]
script = """
cp -a "$CURRENT_DIR/build/make_4.4.1_work/dest/"* "$DESTDIR/"
"""
EOF_MAKE

"${BUILDER}" "${BLAZE_ROOT}/recipes/core/make/recipe.toml"

echo "=== Make 4.4.1 Package Created Successfully ==="
ls -lh "${PKGS_DIR}/make"*
