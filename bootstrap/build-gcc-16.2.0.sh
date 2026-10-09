#!/usr/bin/env bash
# ==============================================================================
# Blaze Universe — Upstream GNU GCC & G++ 16.2.0 Builder
# ==============================================================================
set -euo pipefail

BLAZE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK_DIR="${BLAZE_ROOT}/build/gcc_16.2_work"
SOURCES_DIR="${BLAZE_ROOT}/build/sources"
PKGS_DIR="${BLAZE_ROOT}/build/packages"
BUILDER="${BLAZE_ROOT}/target/debug/blaze-builder"

GCC_VER="16.2.0"
GCC_TAR="gcc-${GCC_VER}.tar.xz"
JOBS="${JOBS:-$(nproc)}"

mkdir -p "${WORK_DIR}" "${SOURCES_DIR}" "${PKGS_DIR}"

# 1. Extract GCC source
if [ ! -f "${WORK_DIR}/gcc-${GCC_VER}/configure" ]; then
    echo "Extracting ${GCC_TAR}..."
    rm -rf "${WORK_DIR}/gcc-${GCC_VER}"
    tar -xf "${SOURCES_DIR}/${GCC_TAR}" -C "${WORK_DIR}"
fi

# 2. Extract in-tree prerequisites (GMP, MPFR, MPC, ISL)
cd "${WORK_DIR}/gcc-${GCC_VER}"

if [ ! -d "gmp" ]; then
    echo "Unpacking GMP into GCC source..."
    rm -rf gmp-6.3.0
    tar -xf "${SOURCES_DIR}/gmp-6.3.0.tar.bz2"
    mv gmp-6.3.0 gmp
fi

if [ ! -d "mpfr" ]; then
    echo "Unpacking MPFR into GCC source..."
    rm -rf mpfr-4.2.2
    tar -xf "${SOURCES_DIR}/mpfr-4.2.2.tar.bz2"
    mv mpfr-4.2.2 mpfr
fi

if [ ! -d "mpc" ]; then
    echo "Unpacking MPC into GCC source..."
    rm -rf mpc-1.3.1
    tar -xf "${SOURCES_DIR}/mpc-1.3.1.tar.gz"
    mv mpc-1.3.1 mpc
fi

if [ ! -d "isl" ]; then
    echo "Unpacking ISL into GCC source..."
    rm -rf isl-0.24
    tar -xf "${SOURCES_DIR}/isl-0.24.tar.bz2"
    mv isl-0.24 isl
fi

# 3. Check for versioned patches
PATCH_DIR="${BLAZE_ROOT}/recipes/core/gcc/patches"
if [ -d "${PATCH_DIR}" ]; then
    for p in "${PATCH_DIR}"/*.patch; do
        if [ -f "$p" ]; then
            echo "Applying patch: $p"
            patch -Np1 -i "$p" || true
        fi
    done
fi

# 4. Configure and build GCC
BUILD_DIR="${WORK_DIR}/build"
mkdir -p "${BUILD_DIR}"
cd "${BUILD_DIR}"

if [ ! -f Makefile ]; then
    echo "Configuring GCC ${GCC_VER}..."
    "${WORK_DIR}/gcc-${GCC_VER}/configure" \
        --prefix=/usr \
        --libdir=/usr/lib \
        --enable-languages=c,c++ \
        --enable-default-pie \
        --enable-default-ssp \
        --with-system-zlib \
        --enable-shared \
        --enable-threads=posix \
        --enable-__cxa_atexit \
        --enable-clocale=gnu \
        --disable-multilib \
        --disable-bootstrap \
        --disable-werror
fi

echo "Compiling GCC ${GCC_VER} (Jobs: ${JOBS})..."
make -j"${JOBS}"

# 5. Install into DESTDIR
DEST_DIR="${WORK_DIR}/dest"
rm -rf "${DEST_DIR}"
mkdir -p "${DEST_DIR}"
echo "Installing GCC into DESTDIR..."
make DESTDIR="${DEST_DIR}" install

# If any libraries ended up in usr/lib64, move them to usr/lib for strict UsrMerge
if [ -d "${DEST_DIR}/usr/lib64" ]; then
    mkdir -p "${DEST_DIR}/usr/lib"
    cp -a "${DEST_DIR}/usr/lib64/"* "${DEST_DIR}/usr/lib/"
    rm -rf "${DEST_DIR}/usr/lib64"
fi

# Add standard symlinks
mkdir -p "${DEST_DIR}/usr/lib"
ln -sf gcc "${DEST_DIR}/usr/bin/cc"
ln -sf g++ "${DEST_DIR}/usr/bin/c++"
ln -sf /usr/bin/cpp "${DEST_DIR}/usr/lib/cpp"

# Clean up libtool archives (.la files) and info/man if desired
find "${DEST_DIR}" -name "*.la" -delete
rm -rf "${DEST_DIR}/usr/share/info"

cd "${BLAZE_ROOT}"

# 6. Package gcc 16.2.0
mkdir -p "${BLAZE_ROOT}/recipes/core/gcc"
cat << 'EOF_GCC' > "${BLAZE_ROOT}/recipes/core/gcc/recipe.toml"
[package]
name = "gcc"
version = "16.2.0"
release = 1
architecture = "x86_64"
summary = "The GNU Compiler Collection (C, C++, and runtime libraries)"
description = "GCC provides modern C and C++ compilers, libstdc++, libgcc_s, and internal support tools."
license = "GPL-3.0-or-later WITH GCC-exception-3.1"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://gcc.gnu.org"

[source]
url = "https://ftp.gnu.org/gnu/gcc/gcc-16.2.0/gcc-16.2.0.tar.xz"
sha256 = "e6738e29597f733270731aa90600f37ffdc045079dfc27ec7e8192cc81085c3e"

[dependencies]
requires = ["glibc = 2.44", "binutils = 2.47"]
provides = [
    "gcc = 16.2.0",
    "g++ = 16.2.0",
    "cmd:gcc",
    "cmd:g++",
    "cmd:cc",
    "cmd:c++",
    "cmd:cpp",
    "lib:libgcc_s.so.1",
    "lib:libstdc++.so.6"
]

[build]
script = """
cp -a "$CURRENT_DIR/build/gcc_16.2_work/dest/"* "$DESTDIR/"
"""
EOF_GCC

"${BUILDER}" "${BLAZE_ROOT}/recipes/core/gcc/recipe.toml"

echo "=== GCC 16.2.0 Package Created Successfully ==="
ls -lh "${PKGS_DIR}/gcc"*
