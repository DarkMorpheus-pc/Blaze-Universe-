#!/usr/bin/env bash
# ==============================================================================
# Blaze Universe — Prepare 64 GB VirtIO Build Disk
# ==============================================================================
set -euo pipefail

BLAZE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="${BLAZE_ROOT}/build"
STAGING_DIR="${BUILD_DIR}/build_disk_staging"
BUILD_DISK_IMG="${BUILD_DIR}/blaze-build-disk.raw"

echo "=== Preparing 64 GB Build Disk Staging ==="
mkdir -p "${STAGING_DIR}/sources"
mkdir -p "${STAGING_DIR}/recipes"
mkdir -p "${STAGING_DIR}/rust-workspace"
mkdir -p "${STAGING_DIR}/gen1-pkgs"
mkdir -p "${STAGING_DIR}/gen2-pkgs"
mkdir -p "${STAGING_DIR}/reports"

# 1. Copy sources
echo "Copying source archives to staging..."
cp -a "${BUILD_DIR}/sources"/* "${STAGING_DIR}/sources/"

# 2. Copy recipes
echo "Copying recipes to staging..."
cp -a "${BLAZE_ROOT}/recipes"/* "${STAGING_DIR}/recipes/"

# 3. Setup rust-workspace with vendored dependencies
echo "Setting up rust workspace..."
cp -a "${BLAZE_ROOT}/Cargo.toml" "${STAGING_DIR}/rust-workspace/"
cp -a "${BLAZE_ROOT}/Cargo.lock" "${STAGING_DIR}/rust-workspace/"
cp -a "${BLAZE_ROOT}/crates" "${STAGING_DIR}/rust-workspace/"

if [ ! -d "${STAGING_DIR}/rust-workspace/vendor" ]; then
    echo "Vendoring cargo dependencies..."
    (
        cd "${BLAZE_ROOT}"
        cargo vendor "${STAGING_DIR}/rust-workspace/vendor"
    )
fi

mkdir -p "${STAGING_DIR}/rust-workspace/.cargo"
cat << 'EOF_CARGO_CFG' > "${STAGING_DIR}/rust-workspace/.cargo/config.toml"
[source.crates-io]
replace-with = "vendored-sources"

[source.vendored-sources]
directory = "vendor"
EOF_CARGO_CFG

# 4. Create in-VM Stage 3 Runner Script
cat << 'EOF_RUNNER' > "${STAGING_DIR}/stage3-runner.sh"
#!/usr/bin/env bash
# ==============================================================================
# BlazeOS In-VM Native Self-Hosting Automation Script (Stage 3.6 & 3.7)
# ==============================================================================
set -euo pipefail

export PATH="/usr/bin:/bin:/usr/sbin:/sbin"
export JOBS="$(nproc)"
BUILD_ROOT="/build"
SOURCES_DIR="${BUILD_ROOT}/sources"
GEN1_WORK="${BUILD_ROOT}/gen1-work"
GEN1_PKGS="${BUILD_ROOT}/gen1-pkgs"
GEN2_WORK="${BUILD_ROOT}/gen2-work"
GEN2_PKGS="${BUILD_ROOT}/gen2-pkgs"
RUST_WS="${BUILD_ROOT}/rust-workspace"
REPORTS_DIR="${BUILD_ROOT}/reports"

mkdir -p "${GEN1_WORK}" "${GEN1_PKGS}" "${GEN2_WORK}" "${GEN2_PKGS}" "${REPORTS_DIR}"

echo "======================================================================"
echo "          BLAZE NATIVE MILESTONE 3: FULL SELF-HOSTING PIPELINE        "
echo "======================================================================"
echo "[INFO] Running on: $(uname -a)"
echo "[INFO] GCC Version: $(gcc --version | head -n1)"
echo "[INFO] Rust Version: $(rustc --version)"
echo "[INFO] Cargo Version: $(cargo --version)"
echo "[INFO] CPUs available: ${JOBS}"
echo "======================================================================"

# ------------------------------------------------------------------------------
# Function: build_binutils
# ------------------------------------------------------------------------------
build_binutils() {
    local gen="$1"
    local work_dir="$2"
    local pkgs_dir="$3"
    echo "--- [${gen}] Building Binutils 2.47 ---"
    if [ -f "${pkgs_dir}/binutils-2.47-1.x86_64.blz" ]; then
        echo "[${gen}] Binutils 2.47 already packaged, skipping build."
        return 0
    fi
    local pkg_work="${work_dir}/binutils-2.47"
    rm -rf "${pkg_work}"
    mkdir -p "${pkg_work}"
    
    tar -xf "${SOURCES_DIR}/binutils-2.47.tar.xz" -C "${pkg_work}"
    local bld_dir="${pkg_work}/build"
    mkdir -p "${bld_dir}"
    cd "${bld_dir}"
    
    "${pkg_work}/binutils-2.47/configure" \
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
        --disable-nls \
        --without-debuginfod
        
    make -j"${JOBS}" tooldir=/usr
    
    local dest_dir="${pkg_work}/dest"
    rm -rf "${dest_dir}"
    mkdir -p "${dest_dir}"
    make tooldir=/usr DESTDIR="${dest_dir}" install
    
    find "${dest_dir}" -name "*.la" -delete
    rm -rf "${dest_dir}/usr/share/info"
    
    # Create recipe and package
    cat << EOF_RECIPE > "${pkg_work}/recipe.toml"
[package]
name = "binutils"
version = "2.47"
release = 1
architecture = "x86_64"
summary = "GNU Binutils (${gen} native build)"
description = "GNU binary utilities compiled inside BlazeOS (${gen})."
license = "GPL-3.0-or-later"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://www.gnu.org/software/binutils/"

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
cp -a "${dest_dir}/"* "\$DESTDIR/"
"""
EOF_RECIPE

    blaze-builder "${pkg_work}/recipe.toml" --output-dir "${pkgs_dir}"
    echo "[${gen}] Binutils 2.47 build complete!"
}

# ------------------------------------------------------------------------------
# Function: build_glibc
# ------------------------------------------------------------------------------
build_glibc() {
    local gen="$1"
    local work_dir="$2"
    local pkgs_dir="$3"
    echo "--- [${gen}] Building Glibc 2.44 ---"
    if [ -f "${pkgs_dir}/glibc-2.44-1.x86_64.blz" ] && [ -f "${pkgs_dir}/glibc-devel-2.44-1.x86_64.blz" ]; then
        echo "[${gen}] Glibc and Glibc-devel 2.44 already packaged, skipping build."
        return 0
    fi
    local pkg_work="${work_dir}/glibc-2.44"
    rm -rf "${pkg_work}"
    mkdir -p "${pkg_work}"
    
    tar -xf "${SOURCES_DIR}/glibc-2.44.tar.xz" -C "${pkg_work}"
    local bld_dir="${pkg_work}/build"
    mkdir -p "${bld_dir}"
    cd "${bld_dir}"
    
    "${pkg_work}/glibc-2.44/configure" \
        --prefix=/usr \
        --disable-profile \
        --enable-kernel=4.19 \
        --enable-stack-protector=strong \
        --disable-nscd \
        libc_cv_slibdir=/usr/lib
        
    make -j"${JOBS}"
    
    local master_dest="${pkg_work}/master-dest"
    rm -rf "${master_dest}"
    mkdir -p "${master_dest}"
    make DESTDIR="${master_dest}" install
    
    # Strict UsrMerge
    if [ -d "${master_dest}/sbin" ]; then
        mkdir -p "${master_dest}/usr/bin"
        mv "${master_dest}/sbin/"* "${master_dest}/usr/bin/"
        rm -rf "${master_dest}/sbin"
    fi
    if [ -d "${master_dest}/usr/sbin" ]; then
        mkdir -p "${master_dest}/usr/bin"
        mv "${master_dest}/usr/sbin/"* "${master_dest}/usr/bin/"
        rm -rf "${master_dest}/usr/sbin"
    fi
    rm -rf "${master_dest}/lib64"
    
    local runtime_dest="${pkg_work}/glibc-runtime-dest"
    local devel_dest="${pkg_work}/glibc-devel-dest"
    rm -rf "${runtime_dest}" "${devel_dest}"
    mkdir -p "${runtime_dest}" "${devel_dest}"
    
    if [ -d "${master_dest}/usr/include" ]; then
        mkdir -p "${devel_dest}/usr"
        mv "${master_dest}/usr/include" "${devel_dest}/usr/"
    fi
    
    mkdir -p "${devel_dest}/usr/lib"
    for f in "${master_dest}/usr/lib"/crt*.o "${master_dest}/usr/lib"/*crt*.o "${master_dest}/usr/lib"/*.a; do
        if [ -f "$f" ]; then
            mv "$f" "${devel_dest}/usr/lib/"
        fi
    done
    
    [ -f "${master_dest}/usr/lib/libc.so" ] && mv "${master_dest}/usr/lib/libc.so" "${devel_dest}/usr/lib/"
    [ -f "${master_dest}/usr/lib/libm.so" ] && mv "${master_dest}/usr/lib/libm.so" "${devel_dest}/usr/lib/"
    
    cp -a "${master_dest}/"* "${runtime_dest}/"
    
    # Package glibc (runtime)
    cat << EOF_GLIBC > "${pkg_work}/recipe-glibc.toml"
[package]
name = "glibc"
version = "2.44"
release = 1
architecture = "x86_64"
summary = "GNU C Library (${gen} native build)"
description = "Core C runtime compiled inside BlazeOS (${gen})."
license = "LGPL-2.1-or-later"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://www.gnu.org/software/libc/"

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
cp -a "${runtime_dest}/"* "\$DESTDIR/"
"""
EOF_GLIBC

    blaze-builder "${pkg_work}/recipe-glibc.toml" --output-dir "${pkgs_dir}"
    
    # Package glibc-devel (headers & stubs)
    cat << EOF_GLIBC_DEVEL > "${pkg_work}/recipe-glibc-devel.toml"
[package]
name = "glibc-devel"
version = "2.44"
release = 1
architecture = "x86_64"
summary = "GNU C Library Headers and Devel Stubs (${gen})"
description = "Development headers and static archives (${gen})."
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
cp -a "${devel_dest}/"* "\$DESTDIR/"
"""
EOF_GLIBC_DEVEL

    blaze-builder "${pkg_work}/recipe-glibc-devel.toml" --output-dir "${pkgs_dir}"
    echo "[${gen}] Glibc & Glibc-devel 2.44 build complete!"
}

# ------------------------------------------------------------------------------
# Function: build_gcc
# ------------------------------------------------------------------------------
build_gcc() {
    local gen="$1"
    local work_dir="$2"
    local pkgs_dir="$3"
    echo "--- [${gen}] Building GCC 16.2.0 ---"
    if [ -f "${pkgs_dir}/gcc-16.2.0-1.x86_64.blz" ]; then
        echo "[${gen}] GCC 16.2.0 already packaged, skipping build."
        return 0
    fi
    local pkg_work="${work_dir}/gcc-16.2.0"
    local bld_dir="${pkg_work}/build"
    
    if [ ! -f "${bld_dir}/Makefile" ]; then
        rm -rf "${pkg_work}"
        mkdir -p "${pkg_work}"
        
        tar -xf "${SOURCES_DIR}/gcc-16.2.0.tar.xz" -C "${pkg_work}"
        cd "${pkg_work}/gcc-16.2.0"
        
        # Extract in-tree prerequisites
        tar -xf "${SOURCES_DIR}/gmp-6.3.0.tar.bz2" && mv gmp-6.3.0 gmp
        tar -xf "${SOURCES_DIR}/mpfr-4.2.2.tar.bz2" && mv mpfr-4.2.2 mpfr
        tar -xf "${SOURCES_DIR}/mpc-1.3.1.tar.gz" && mv mpc-1.3.1 mpc
        tar -xf "${SOURCES_DIR}/isl-0.24.tar.bz2" && mv isl-0.24 isl
        
        mkdir -p "${bld_dir}"
        cd "${bld_dir}"
        
        "${pkg_work}/gcc-16.2.0/configure" \
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
    else
        echo "[${gen}] Found existing Makefile in ${bld_dir}, resuming build directly..."
        find "${bld_dir}" -type f -size 0 -delete 2>/dev/null || true
        cd "${bld_dir}"
    fi
        
    make -j"${JOBS}"
    
    local dest_dir="${pkg_work}/dest"
    rm -rf "${dest_dir}"
    mkdir -p "${dest_dir}"
    make DESTDIR="${dest_dir}" install
    
    if [ -d "${dest_dir}/usr/lib64" ]; then
        mkdir -p "${dest_dir}/usr/lib"
        cp -a "${dest_dir}/usr/lib64/"* "${dest_dir}/usr/lib/"
        rm -rf "${dest_dir}/usr/lib64"
    fi
    
    mkdir -p "${dest_dir}/usr/lib"
    ln -sf gcc "${dest_dir}/usr/bin/cc"
    ln -sf g++ "${dest_dir}/usr/bin/c++"
    ln -sf /usr/bin/cpp "${dest_dir}/usr/lib/cpp"
    
    find "${dest_dir}" -name "*.la" -delete
    rm -rf "${dest_dir}/usr/share/info"
    
    cat << EOF_GCC > "${pkg_work}/recipe.toml"
[package]
name = "gcc"
version = "16.2.0"
release = 1
architecture = "x86_64"
summary = "GNU Compiler Collection (${gen} native build)"
description = "GCC C/C++ compiler and runtime compiled inside BlazeOS (${gen})."
license = "GPL-3.0-or-later WITH GCC-exception-3.1"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://gcc.gnu.org"

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
cp -a "${dest_dir}/"* "\$DESTDIR/"
"""
EOF_GCC

    blaze-builder "${pkg_work}/recipe.toml" --output-dir "${pkgs_dir}"
    echo "[${gen}] GCC 16.2.0 build complete!"
}

# ==============================================================================
# STAGE 3.6: NATIVE C/C++ TOOLCHAIN BOOTSTRAP (Gen 1 & Gen 2)
# ==============================================================================
echo ">>> STARTING STAGE 3.6: Gen 1 Toolchain Build (Built using Gen 0) <<<"
[ -f "${GEN1_PKGS}/binutils-2.47-1.x86_64.blz" ] || build_binutils "Gen1" "${GEN1_WORK}" "${GEN1_PKGS}"
[ -f "${GEN1_PKGS}/glibc-2.44-1.x86_64.blz" ] || build_glibc "Gen1" "${GEN1_WORK}" "${GEN1_PKGS}"
[ -f "${GEN1_PKGS}/gcc-16.2.0-1.x86_64.blz" ] || build_gcc "Gen1" "${GEN1_WORK}" "${GEN1_PKGS}"

echo "[STAGE 3.6] Gen 1 Packages generated:"
ls -lh "${GEN1_PKGS}"/

echo ">>> Installing Gen 1 Toolchain via Portadora <<<"
portadora install "${GEN1_PKGS}"/binutils-*.blz "${GEN1_PKGS}"/glibc-*.blz "${GEN1_PKGS}"/gcc-*.blz

echo ">>> Validating Active Gen 1 Compiler & Environment <<<"
mkdir -p "${REPORTS_DIR}"
gcc -v 2>&1 | tee "${REPORTS_DIR}/gen1_gcc_specs.txt"
ld -v 2>&1 | tee "${REPORTS_DIR}/gen1_ld_version.txt"

cat << 'EOF_PROV' > /tmp/provenance_test.c
#include <stdio.h>
#include <stdlib.h>
int main() {
    printf("BlazeOS Native Toolchain Provenance Test OK\n");
    return 0;
}
EOF_PROV

gcc -v -Wl,--verbose /tmp/provenance_test.c -o /tmp/provenance_test 2>&1 | tee "${REPORTS_DIR}/gen1_provenance.txt"
/tmp/provenance_test

echo ">>> STARTING STAGE 3.6: Gen 2 Toolchain Build (Built using Gen 1) <<<"
[ -f "${GEN2_PKGS}/binutils-2.47-1.x86_64.blz" ] || build_binutils "Gen2" "${GEN2_WORK}" "${GEN2_PKGS}"
[ -f "${GEN2_PKGS}/glibc-2.44-1.x86_64.blz" ] || build_glibc "Gen2" "${GEN2_WORK}" "${GEN2_PKGS}"
[ -f "${GEN2_PKGS}/gcc-16.2.0-1.x86_64.blz" ] || build_gcc "Gen2" "${GEN2_WORK}" "${GEN2_PKGS}"

echo "[STAGE 3.6] Gen 2 Packages generated:"
ls -lh "${GEN2_PKGS}"/

echo ">>> Comparing Gen 1 vs Gen 2 Toolchain Binaries & Provenance <<<"
report_file="${REPORTS_DIR}/gen1_gen2_comparison.txt"
{
    echo "================================================================="
    echo "       BLAZE NATIVE TOOLCHAIN SELF-HOSTING COMPARISON REPORT     "
    echo "================================================================="
    echo "Date: $(date -u)"
    echo "Host Kernel: $(uname -a)"
    echo "Gen 1 Compiler: $(gcc --version | head -n1)"
    echo ""
    echo "--- SHA-256 Checksums of Toolchain Packages ---"
    echo "Gen 1 Packages:"
    sha256sum "${GEN1_PKGS}"/*.blz
    echo ""
    echo "Gen 2 Packages:"
    sha256sum "${GEN2_PKGS}"/*.blz
    echo ""
    echo "--- Binary Comparison of Core Toolchain Binaries ---"
    for bin in "binutils-2.47/dest/usr/bin/ld.bfd" "binutils-2.47/dest/usr/bin/as" "gcc-16.2.0/dest/usr/bin/gcc" "gcc-16.2.0/dest/usr/bin/g++"; do
        f1="${GEN1_WORK}/${bin}"
        f2="${GEN2_WORK}/${bin}"
        if [ -f "$f1" ] && [ -f "$f2" ]; then
            h1=$(sha256sum "$f1" | awk '{print $1}')
            h2=$(sha256sum "$f2" | awk '{print $1}')
            echo "Binary: ${bin}"
            echo "  Gen 1 SHA256: ${h1}"
            echo "  Gen 2 SHA256: ${h2}"
            if [ "$h1" = "$h2" ]; then
                echo "  Status: BIT-FOR-BIT IDENTICAL"
            else
                echo "  Status: Binary diff present (analyzing ELF sections...)"
                readelf -S "$f1" > /tmp/s1.txt || true
                readelf -S "$f2" > /tmp/s2.txt || true
                diff -u /tmp/s1.txt /tmp/s2.txt || true
            fi
        fi
    done
} | tee "${report_file}"
sync

# ==============================================================================
# STAGE 3.7: RUST TOOLCHAIN & NATIVE BLAZE TOOLING (Portadora & blaze-builder)
# ==============================================================================
echo "======================================================================"
echo ">>> STARTING STAGE 3.7: Native Compilation of Blaze Tooling in Rust <<<"
echo "======================================================================"

rust_report="${REPORTS_DIR}/rust_bootstrap_provenance.txt"
{
    echo "================================================================="
    echo "          BLAZE RUST BOOTSTRAP & TOOLING PROVENANCE REPORT       "
    echo "================================================================="
    echo "Date: $(date -u)"
    echo "Rustc Version: $(rustc --version)"
    echo "Cargo Version: $(cargo --version)"
    echo "Bootstrap Origin: Official upstream standalone Rust 1.98.1 x86_64 binary release"
    echo "Compiler Status: rustc is an imported bootstrap compiler (not rebuilt from source)."
    echo "Blaze Tooling Status: portadora and blaze-builder are compiled NATIVELY inside BlazeOS"
    echo "Dependency Mode: 100% OFFLINE, LOCKED against vendored crates (/build/rust-workspace/vendor)"
} | tee "${rust_report}"
sync

echo ">>> Installing pkgconf and openssl-devel build dependencies via Portadora <<<"
portadora install /build/packages/pkgconf-*.blz /build/packages/openssl-devel-*.blz

echo "--- Verifying pkg-config and OpenSSL dev metadata ---"
pkg-config --version
pkg-config --libs --cflags openssl

# Ensure target-specific linker symlink exists for rustc/cargo
[ -e /usr/bin/x86_64-linux-gnu-gcc ] || ln -sf gcc /usr/bin/x86_64-linux-gnu-gcc
export CC="gcc"
export CXX="g++"
export RUSTFLAGS="-C linker=gcc"

mkdir -p "${RUST_WS}/.cargo"
cat << 'EOF_CRG' > "${RUST_WS}/.cargo/config.toml"
[source.crates-io]
replace-with = "vendored-sources"

[source.vendored-sources]
directory = "vendor"

[target.x86_64-unknown-linux-gnu]
linker = "/usr/bin/gcc"
EOF_CRG

cd "${RUST_WS}"
echo "[STAGE 3.7] Building portadora and blaze-builder from source inside BlazeOS..."
cargo build --release --offline --locked -p portadora -p blaze-builder

echo "[STAGE 3.7] Build Complete! Inspecting generated binaries:"
new_portadora="${RUST_WS}/target/release/portadora"
new_builder="${RUST_WS}/target/release/blaze-builder"
ls -lh "${new_portadora}" "${new_builder}"

echo "[STAGE 3.7] ABI and Contamination Audit for Newly Compiled Binaries:"
echo "--- Interpreter Check ---"
readelf -l "${new_portadora}" | grep interpreter
readelf -l "${new_builder}" | grep interpreter

echo "--- Dynamic Section / RPATH Check ---"
readelf -d "${new_portadora}" | grep -E 'RPATH|RUNPATH' || echo "PORTADORA_RPATH_CLEAN: OK"
readelf -d "${new_builder}" | grep -E 'RPATH|RUNPATH' || echo "BLAZE_BUILDER_RPATH_CLEAN: OK"

echo "--- Dynamic Dependencies (NEEDED) ---"
readelf -d "${new_portadora}" | grep NEEDED
readelf -d "${new_builder}" | grep NEEDED

echo "--- Functional Test of Native Binaries ---"
"${new_portadora}" --version
"${new_builder}" --version

echo "--- Functional Test: Creating and Installing a Package using New Binaries ---"
mkdir -p /tmp/selfhost-test-pkg
cat << 'EOF_TEST' > /tmp/selfhost-test-pkg/recipe.toml
[package]
name = "selfhost-smoke-test"
version = "1.0.0"
release = 1
architecture = "x86_64"
summary = "Milestone 3 Self-Hosting Functional Verification Package"
description = "A smoke test package built and installed with the newly compiled tools."
license = "MIT"
maintainer = "BlazeOS Core Team <core@blazeos.org>"

[dependencies]
provides = ["selfhost-smoke-test = 1.0.0"]

[build]
script = """
mkdir -p "$DESTDIR/usr/share/blazeos"
echo "BlazeOS Self-Hosting Milestone 3 Verified" > "$DESTDIR/usr/share/blazeos/selfhost_token.txt"
"""
EOF_TEST

"${new_builder}" /tmp/selfhost-test-pkg/recipe.toml --output-dir /tmp/selfhost-test-pkg
ls -lh /tmp/selfhost-test-pkg/*.blz

"${new_portadora}" install /tmp/selfhost-test-pkg/*.blz
cat /usr/share/blazeos/selfhost_token.txt

# Package newly built portadora & blaze-builder natively
echo ">>> Packaging Self-Hosted Portadora & Blaze-Builder Packages <<<"
mkdir -p /tmp/selfhost-tooling-pkgs
cat << 'EOF_PORTADORA_RECIPE' > /tmp/selfhost-tooling-pkgs/recipe-portadora.toml
[package]
name = "portadora"
version = "0.1.0"
release = 2
architecture = "x86_64"
summary = "Native package manager for BlazeOS (Self-Hosted native build)"
description = "High-performance transactional package manager compiled inside BlazeOS."
license = "MIT OR Apache-2.0"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://blazeos.org"

[dependencies]
requires = ["glibc >= 2.38"]
provides = [
    "cmd:portadora",
    "portadora = 0.1.0"
]

[build]
script = """
mkdir -p "$DESTDIR/usr/bin"
mkdir -p "$DESTDIR/var/lib/portadora"
cp -a "/build/rust-workspace/target/release/portadora" "$DESTDIR/usr/bin/portadora"
"""
EOF_PORTADORA_RECIPE

cat << 'EOF_BUILDER_RECIPE' > /tmp/selfhost-tooling-pkgs/recipe-builder.toml
[package]
name = "blaze-builder"
version = "0.1.0"
release = 2
architecture = "x86_64"
summary = "Package build engine for BlazeOS (Self-Hosted native build)"
description = "Deterministic package builder compiled inside BlazeOS."
license = "MIT OR Apache-2.0"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://blazeos.org"

[dependencies]
requires = ["glibc >= 2.38"]
provides = [
    "cmd:blaze-builder",
    "blaze-builder = 0.1.0"
]

[build]
script = """
mkdir -p "$DESTDIR/usr/bin"
cp -a "/build/rust-workspace/target/release/blaze-builder" "$DESTDIR/usr/bin/blaze-builder"
"""
EOF_BUILDER_RECIPE

"${new_builder}" /tmp/selfhost-tooling-pkgs/recipe-portadora.toml --output-dir /tmp/selfhost-tooling-pkgs
"${new_builder}" /tmp/selfhost-tooling-pkgs/recipe-builder.toml --output-dir /tmp/selfhost-tooling-pkgs

echo ">>> Upgrading System Portadora & Blaze-Builder using Newly Built Packages <<<"
"${new_portadora}" install /tmp/selfhost-tooling-pkgs/portadora-*.blz /tmp/selfhost-tooling-pkgs/blaze-builder-*.blz

# ==============================================================================
# FINAL QUALITY GATES & SYSTEM VERIFICATION
# ==============================================================================
echo "======================================================================"
echo ">>> RUNNING FINAL SYSTEM INTEGRITY AUDIT <<<"
echo "======================================================================"

echo "--- Portadora Full Verification ---"
portadora verify

echo "--- Systemd State ---"
systemctl is-system-running || true
sync

echo "======================================================================"
echo "      MILESTONE 3 SELF-HOSTING PIPELINE COMPLETED SUCCESSFULLY!       "
echo "======================================================================"
EOF_RUNNER
chmod +x "${STAGING_DIR}/stage3-runner.sh"

# 5. Populate ext4 build disk image using mke2fs -d
echo "Generating 64 GB ext4 build disk image (${BUILD_DISK_IMG})..."
rm -f "${BUILD_DISK_IMG}"
# Create 64GB sparse file
truncate -s 64G "${BUILD_DISK_IMG}"
mke2fs -d "${STAGING_DIR}" -t ext4 -L blaze-build "${BUILD_DISK_IMG}"

echo "=== Build Disk Image Ready ==="
ls -lh "${BUILD_DISK_IMG}"
