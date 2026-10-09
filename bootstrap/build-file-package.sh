#!/usr/bin/env bash
set -euo pipefail

BLAZE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK_DIR="${BLAZE_ROOT}/build/file_work"
PKGS_DIR="${BLAZE_ROOT}/build/packages"
BUILDER="${BLAZE_ROOT}/target/release/blaze-builder"

mkdir -p "${WORK_DIR}" "${PKGS_DIR}"
DEST_DIR="${WORK_DIR}/dest"
rm -rf "${DEST_DIR}"
mkdir -p "${DEST_DIR}/usr/bin" "${DEST_DIR}/usr/lib" "${DEST_DIR}/usr/share/misc"

cp -a /usr/bin/file "${DEST_DIR}/usr/bin/"
cp -a /usr/lib/libmagic*.so* "${DEST_DIR}/usr/lib/"
cp -a /usr/share/misc/magic* "${DEST_DIR}/usr/share/misc/" 2>/dev/null || true

mkdir -p "${BLAZE_ROOT}/recipes/core/file"
cat << 'EOF_RECIPE' > "${BLAZE_ROOT}/recipes/core/file/recipe.toml"
[package]
name = "file"
version = "5.45"
release = 1
architecture = "x86_64"
summary = "File type identification utility and libmagic"
description = "Determines file type using magic numbers and file headers."
license = "BSD-2-Clause"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://www.darwinsys.com/file/"

[dependencies]
requires = ["glibc = 2.44", "zlib = 1.3.1", "zstd = 1.5.6", "bzip2 = 1.0.8", "xz = 5.6.2"]
provides = [
    "file = 5.45",
    "cmd:file",
    "lib:libmagic.so.1"
]

[triggers]
run_ldconfig = true

[build]
script = """
cp -a "$CURRENT_DIR/build/file_work/dest/"* "$DESTDIR/"
"""
EOF_RECIPE

"${BUILDER}" "${BLAZE_ROOT}/recipes/core/file/recipe.toml"

echo "=== File Package Created Successfully ==="
ls -lh "${PKGS_DIR}/file"*
