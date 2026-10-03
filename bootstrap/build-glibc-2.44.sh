#!/usr/bin/env bash
# ==============================================================================
# Blaze Universe — Upstream Glibc 2.44 Source Builder & Runtime/Devel Splitter
# ==============================================================================
set -euo pipefail

BLAZE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK_DIR="${BLAZE_ROOT}/build/glibc_2.44_work"
SOURCES_DIR="${BLAZE_ROOT}/build/sources"
PKGS_DIR="${BLAZE_ROOT}/build/packages"
BUILDER="${BLAZE_ROOT}/target/debug/blaze-builder"

GLIBC_VER="2.44"
GLIBC_TAR="glibc-${GLIBC_VER}.tar.xz"
JOBS="${JOBS:-$(nproc)}"

mkdir -p "${WORK_DIR}" "${SOURCES_DIR}" "${PKGS_DIR}"

# 1. Extract
if [ ! -d "${WORK_DIR}/glibc-${GLIBC_VER}" ]; then
    echo "Extracting ${GLIBC_TAR}..."
    tar -xf "${SOURCES_DIR}/${GLIBC_TAR}" -C "${WORK_DIR}"
fi

# 2. Check for versioned patches
PATCH_DIR="${BLAZE_ROOT}/recipes/core/glibc/patches"
if [ -d "${PATCH_DIR}" ]; then
    for p in "${PATCH_DIR}"/*.patch; do
        if [ -f "$p" ]; then
            echo "Applying patch: $p"
            patch -d "${WORK_DIR}/glibc-${GLIBC_VER}" -Np1 -i "$p" || true
        fi
    done
fi

# 3. Configure and build glibc
BUILD_DIR="${WORK_DIR}/build"
mkdir -p "${BUILD_DIR}"
cd "${BUILD_DIR}"

if [ ! -f Makefile ]; then
    echo "Configuring glibc ${GLIBC_VER}..."
    "${WORK_DIR}/glibc-${GLIBC_VER}/configure" \
        --prefix=/usr \
        --disable-profile \
        --enable-kernel=4.19 \
        --enable-stack-protector=strong \
        --disable-nscd \
        libc_cv_slibdir=/usr/lib
fi

echo "Compiling glibc ${GLIBC_VER} (Jobs: ${JOBS})..."
make -j"${JOBS}"

# 4. Install into master DESTDIR
MASTER_DEST="${WORK_DIR}/master-dest"
rm -rf "${MASTER_DEST}"
mkdir -p "${MASTER_DEST}"
echo "Installing glibc into master DESTDIR..."
make DESTDIR="${MASTER_DEST}" install

# Enforce strict UsrMerge in master DESTDIR:
# 1. Move sbin binaries to usr/bin and remove sbin
if [ -d "${MASTER_DEST}/sbin" ]; then
    mkdir -p "${MASTER_DEST}/usr/bin"
    mv "${MASTER_DEST}/sbin/"* "${MASTER_DEST}/usr/bin/"
    rm -rf "${MASTER_DEST}/sbin"
fi

# 2. Move usr/sbin binaries to usr/bin and remove usr/sbin
if [ -d "${MASTER_DEST}/usr/sbin" ]; then
    mkdir -p "${MASTER_DEST}/usr/bin"
    mv "${MASTER_DEST}/usr/sbin/"* "${MASTER_DEST}/usr/bin/"
    rm -rf "${MASTER_DEST}/usr/sbin"
fi

# 3. Remove lib64 directory (filesystem package provides the root /lib64 -> usr/lib symlink)
rm -rf "${MASTER_DEST}/lib64"

# 5. Partition master DESTDIR into glibc (runtime) and glibc-devel (development)
RUNTIME_DEST="${WORK_DIR}/glibc-runtime-dest"
DEVEL_DEST="${WORK_DIR}/glibc-devel-dest"
rm -rf "${RUNTIME_DEST}" "${DEVEL_DEST}"
mkdir -p "${RUNTIME_DEST}" "${DEVEL_DEST}"

# Move headers (/usr/include) to glibc-devel
if [ -d "${MASTER_DEST}/usr/include" ]; then
    mkdir -p "${DEVEL_DEST}/usr"
    mv "${MASTER_DEST}/usr/include" "${DEVEL_DEST}/usr/"
fi

# Move static libraries (*.a), CRT objects (crt*.o), and libc.so ldscript to glibc-devel
mkdir -p "${DEVEL_DEST}/usr/lib"
for f in "${MASTER_DEST}/usr/lib"/crt*.o "${MASTER_DEST}/usr/lib"/*crt*.o "${MASTER_DEST}/usr/lib"/*.a; do
    if [ -f "$f" ]; then
        mv "$f" "${DEVEL_DEST}/usr/lib/"
    fi
done

# If /usr/lib/libc.so is a text ld script, it belongs in glibc-devel!
if [ -f "${MASTER_DEST}/usr/lib/libc.so" ] && file "${MASTER_DEST}/usr/lib/libc.so" | grep -q "ASCII text"; then
    mv "${MASTER_DEST}/usr/lib/libc.so" "${DEVEL_DEST}/usr/lib/"
fi
# Similarly for libm.so if text script
if [ -f "${MASTER_DEST}/usr/lib/libm.so" ] && file "${MASTER_DEST}/usr/lib/libm.so" | grep -q "ASCII text"; then
    mv "${MASTER_DEST}/usr/lib/libm.so" "${DEVEL_DEST}/usr/lib/"
fi

# Everything remaining in MASTER_DEST is runtime!
cp -a "${MASTER_DEST}/"* "${RUNTIME_DEST}/"

cd "${BLAZE_ROOT}"

# 6. Package glibc 2.44 (runtime)
cat << 'EOF_GLIBC' > "${BLAZE_ROOT}/recipes/core/glibc/recipe.toml"
[package]
name = "glibc"
version = "2.44"
release = 1
architecture = "x86_64"
summary = "GNU C Library"
description = "The GNU C Library provides the core runtime libraries and dynamic linker for BlazeOS."
license = "LGPL-2.1-or-later"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://www.gnu.org/software/libc/"

[source]
url = "https://ftp.gnu.org/gnu/glibc/glibc-2.44.tar.xz"
sha256 = "37f600f2bef3c5e8300147059568b2a2e40a7ad6ccc65ce942556d49429cc667"

[dependencies]
provides = [
    "glibc = 2.44",
    "lib:libc.so.6",
    "lib:libm.so.6",
    "lib:libpthread.so.0",
    "lib:ld-linux-x86-64.so.2"
]

[build]
script = """
cp -a "$CURRENT_DIR/build/glibc_2.44_work/glibc-runtime-dest/"* "$DESTDIR/"
"""
EOF_GLIBC

"${BUILDER}" "${BLAZE_ROOT}/recipes/core/glibc/recipe.toml"

# 7. Package glibc-devel 2.44 (development)
mkdir -p "${BLAZE_ROOT}/recipes/core/glibc-devel"
cat << 'EOF_GLIBC_DEVEL' > "${BLAZE_ROOT}/recipes/core/glibc-devel/recipe.toml"
[package]
name = "glibc-devel"
version = "2.44"
release = 1
architecture = "x86_64"
summary = "GNU C Library Headers, CRT Objects, and Development Stubs"
description = "Development headers, static archives, and linker scripts for glibc."
license = "LGPL-2.1-or-later"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://www.gnu.org/software/libc/"

[dependencies]
requires = ["glibc = 2.44"]
provides = [
    "glibc-devel = 2.44"
]

[build]
script = """
cp -a "$CURRENT_DIR/build/glibc_2.44_work/glibc-devel-dest/"* "$DESTDIR/"
"""
EOF_GLIBC_DEVEL

"${BUILDER}" "${BLAZE_ROOT}/recipes/core/glibc-devel/recipe.toml"

echo "=== Glibc & Glibc-devel 2.44 Packages Created Successfully ==="
ls -lh "${PKGS_DIR}/glibc"*
