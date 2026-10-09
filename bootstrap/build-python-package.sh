#!/usr/bin/env bash
# ==============================================================================
# Blaze Universe — Python Package Builder (Required for Glibc / Kernel builds)
# ==============================================================================
set -euo pipefail

BLAZE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK_DIR="${BLAZE_ROOT}/build/python_work"
PKGS_DIR="${BLAZE_ROOT}/build/packages"
BUILDER="${BLAZE_ROOT}/target/release/blaze-builder"

mkdir -p "${WORK_DIR}" "${PKGS_DIR}"

DEST_DIR="${WORK_DIR}/dest"
rm -rf "${DEST_DIR}"
mkdir -p "${DEST_DIR}/usr/bin" "${DEST_DIR}/usr/lib"

cp -a /usr/bin/python* "${DEST_DIR}/usr/bin/"
cp -a /usr/lib/libpython3*.so* "${DEST_DIR}/usr/lib/"

# Copy standard library excluding site-packages and test
mkdir -p "${DEST_DIR}/usr/lib/python3.14"
cp -a /usr/lib/python3.14/* "${DEST_DIR}/usr/lib/python3.14/" 2>/dev/null || true
rm -rf "${DEST_DIR}/usr/lib/python3.14/site-packages"
rm -rf "${DEST_DIR}/usr/lib/python3.14/test"
rm -rf "${DEST_DIR}/usr/lib/python3.14/idlelib"
mkdir -p "${DEST_DIR}/usr/lib/python3.14/site-packages"

mkdir -p "${BLAZE_ROOT}/recipes/core/python"
cat << 'EOF_RECIPE' > "${BLAZE_ROOT}/recipes/core/python/recipe.toml"
[package]
name = "python"
version = "3.14.7"
release = 1
architecture = "x86_64"
summary = "Python 3 Interpreter and Standard Library"
description = "Python interpreter and standard library required for glibc build tools."
license = "PSF-2.0"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://www.python.org/"

[dependencies]
requires = ["glibc = 2.44"]
provides = [
    "python = 3.14.7",
    "python3 = 3.14.7",
    "cmd:python",
    "cmd:python3",
    "cmd:python3.14",
    "lib:libpython3.14.so.1.0"
]

[triggers]
run_ldconfig = true

[build]
script = """
cp -a "$CURRENT_DIR/build/python_work/dest/"* "$DESTDIR/"
"""
EOF_RECIPE

"${BUILDER}" "${BLAZE_ROOT}/recipes/core/python/recipe.toml"

echo "=== Python Package Created Successfully ==="
ls -lh "${PKGS_DIR}/python"*
