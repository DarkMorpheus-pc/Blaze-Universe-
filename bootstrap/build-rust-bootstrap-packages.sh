#!/usr/bin/env bash
# ==============================================================================
# Blaze Universe — Rust Bootstrap Toolchain & Dependencies Packager
# ==============================================================================
set -euo pipefail

BLAZE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK_DIR="${BLAZE_ROOT}/build/rust_bootstrap_work"
PKGS_DIR="${BLAZE_ROOT}/build/packages"
BUILDER="${BLAZE_ROOT}/target/release/blaze-builder"

mkdir -p "${WORK_DIR}" "${PKGS_DIR}"

echo "=== Packaging Rust Runtime Dependencies ==="
DEPS_DEST="${WORK_DIR}/rust-runtime-deps-dest"
rm -rf "${DEPS_DEST}"
mkdir -p "${DEPS_DEST}/usr/lib"

# Copy needed libraries from host system
PATTERNS=(
    "libLLVM*"
    "libedit*"
    "libffi*"
    "libicu*"
    "libxml2*"
    "libgit2*"
    "libssh2*"
    "libcurl*"
    "libsqlite3*"
    "libllhttp*"
    "libnghttp*"
    "libngtcp2*"
    "libidn2*"
    "libpsl*"
    "libunistring*"
)

for p in "${PATTERNS[@]}"; do
    cp -a /usr/lib/${p} "${DEPS_DEST}/usr/lib/" 2>/dev/null || true
done

mkdir -p "${BLAZE_ROOT}/recipes/core/rust-runtime-deps"
cat << 'EOF_RUST_DEPS' > "${BLAZE_ROOT}/recipes/core/rust-runtime-deps/recipe.toml"
[package]
name = "rust-runtime-deps"
version = "1.0.0"
release = 1
architecture = "x86_64"
summary = "LLVM and auxiliary shared libraries for Rust toolchain"
description = "Runtime dependencies required for rustc and cargo bootstrap compiler."
license = "Apache-2.0 WITH LLVM-exception AND MIT AND BSD-3-Clause"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://rust-lang.org"

[dependencies]
requires = ["glibc = 2.44", "gcc = 16.2.0", "openssl = 3.3.1", "zlib = 1.3.1", "zstd = 1.5.6"]
provides = [
    "rust-runtime-deps = 1.0.0",
    "lib:libLLVM.so.22.1",
    "lib:libedit.so.0",
    "lib:libffi.so.8",
    "lib:libxml2.so.16",
    "lib:libgit2.so.1.9",
    "lib:libssh2.so.1",
    "lib:libcurl.so.4",
    "lib:libsqlite3.so.0"
]

[triggers]
run_ldconfig = true

[build]
script = """
cp -a "$CURRENT_DIR/build/rust_bootstrap_work/rust-runtime-deps-dest/"* "$DESTDIR/"
"""
EOF_RUST_DEPS

"${BUILDER}" "${BLAZE_ROOT}/recipes/core/rust-runtime-deps/recipe.toml"

echo "=== Packaging Rust Bootstrap Toolchain ==="
RUST_DEST="${WORK_DIR}/rust-dest"
rm -rf "${RUST_DEST}"
mkdir -p "${RUST_DEST}/usr/bin" "${RUST_DEST}/usr/lib"

cp -a /usr/bin/rustc "${RUST_DEST}/usr/bin/"
cp -a /usr/bin/cargo "${RUST_DEST}/usr/bin/"
cp -a /usr/lib/librustc_driver*.so "${RUST_DEST}/usr/lib/"
mkdir -p "${RUST_DEST}/usr/lib/rustlib"
cp -a /usr/lib/rustlib/x86_64-unknown-linux-gnu "${RUST_DEST}/usr/lib/rustlib/"

mkdir -p "${BLAZE_ROOT}/recipes/core/rust"
cat << 'EOF_RUST' > "${BLAZE_ROOT}/recipes/core/rust/recipe.toml"
[package]
name = "rust"
version = "1.98.1"
release = 1
architecture = "x86_64"
summary = "The Rust Programming Language (Bootstrap Toolchain)"
description = "Rust compiler (rustc), package manager (cargo), and standard libraries for BlazeOS Native."
license = "MIT OR Apache-2.0"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://www.rust-lang.org/"

[dependencies]
requires = ["glibc = 2.44", "gcc = 16.2.0", "binutils = 2.47", "rust-runtime-deps = 1.0.0"]
provides = [
    "rust = 1.98.1",
    "cargo = 1.98.1",
    "cmd:rustc",
    "cmd:cargo"
]

[triggers]
run_ldconfig = true

[build]
script = """
cp -a "$CURRENT_DIR/build/rust_bootstrap_work/rust-dest/"* "$DESTDIR/"
"""
EOF_RUST

"${BUILDER}" "${BLAZE_ROOT}/recipes/core/rust/recipe.toml"

echo "=== Rust Bootstrap Packages Created Successfully ==="
ls -lh "${PKGS_DIR}/rust"*
