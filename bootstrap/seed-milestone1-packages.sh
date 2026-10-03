#!/usr/bin/env bash
# ==============================================================================
# Blaze Universe — Milestone 1 Fast Seed Package Generator
# ==============================================================================
# Assembles clean, UsrMerged, standalone .blz packages for:
#   - glibc (2.39-1)
#   - bash (5.2.21-1)
#   - coreutils (9.4-1)
# using the native Blaze BlzWriter engine so Milestone 1 chroot can be validated.
# ==============================================================================

set -euo pipefail

BLAZE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK_DIR="${BLAZE_ROOT}/build/seed_work"
PKGS_DIR="${BLAZE_ROOT}/build/packages"
BUILDER="${BLAZE_ROOT}/target/debug/blaze-builder"

mkdir -p "${WORK_DIR}" "${PKGS_DIR}"

echo "=== Generating Base Packages for Milestone 1 Verification ==="

# 1. Ensure filesystem and portadora are built
"${BUILDER}" "${BLAZE_ROOT}/recipes/core/filesystem/recipe.toml"
"${BUILDER}" "${BLAZE_ROOT}/recipes/core/portadora/recipe.toml"

# 2. Package glibc
GLIBC_DEST="${WORK_DIR}/glibc-dest"
rm -rf "${GLIBC_DEST}"
mkdir -p "${GLIBC_DEST}/usr/lib" "${GLIBC_DEST}/usr/bin" "${GLIBC_DEST}/usr/lib/locale" "${GLIBC_DEST}/usr/lib/gconv"

echo "Collecting Glibc libraries, NSS modules, and runtime utilities..."
LIBC_PATH="$(ldd /usr/bin/env | grep 'libc\.so' | awk '{print $3}')"
LIBM_PATH="$(ldd /usr/bin/env | grep 'libm\.so' | awk '{print $3}' || true)"
LD_SO_PATH="$(ldd /usr/bin/env | grep 'ld-linux' | awk '{print $1}')"

cp -a /usr/lib/libc.so* "${GLIBC_DEST}/usr/lib/" 2>/dev/null || cp -a "${LIBC_PATH}"* "${GLIBC_DEST}/usr/lib/"
cp -a /usr/lib/libm.so* "${GLIBC_DEST}/usr/lib/" 2>/dev/null || true
cp -a /usr/lib/libdl.so* "${GLIBC_DEST}/usr/lib/" 2>/dev/null || true
cp -a /usr/lib/libgcc_s.so* "${GLIBC_DEST}/usr/lib/" 2>/dev/null || true
cp -a /usr/lib/libpthread.so* "${GLIBC_DEST}/usr/lib/" 2>/dev/null || true
cp -a /usr/lib/librt.so* "${GLIBC_DEST}/usr/lib/" 2>/dev/null || true
cp -a /usr/lib/libutil.so* "${GLIBC_DEST}/usr/lib/" 2>/dev/null || true
cp -a /usr/lib/libresolv*.so* "${GLIBC_DEST}/usr/lib/" 2>/dev/null || true
cp -a /usr/lib/libcrypt.so* "${GLIBC_DEST}/usr/lib/" 2>/dev/null || true
cp -a /usr/lib/libnss_files*.so* "${GLIBC_DEST}/usr/lib/" 2>/dev/null || true
cp -a /usr/lib/libnss_dns*.so* "${GLIBC_DEST}/usr/lib/" 2>/dev/null || true
cp -a /usr/lib/libnss_compat*.so* "${GLIBC_DEST}/usr/lib/" 2>/dev/null || true
cp -a /usr/lib/libnss_myhostname*.so* "${GLIBC_DEST}/usr/lib/" 2>/dev/null || true
cp -a /usr/lib/ld-linux-x86-64.so* "${GLIBC_DEST}/usr/lib/" 2>/dev/null || cp -a "${LD_SO_PATH}" "${GLIBC_DEST}/usr/lib/"

# Include ldconfig
cp -a /usr/bin/ldconfig "${GLIBC_DEST}/usr/bin/"

# Include C.utf8 locale and basic gconv modules
cp -a /usr/lib/locale/C.utf8 "${GLIBC_DEST}/usr/lib/locale/" 2>/dev/null || true
cp -a /usr/lib/gconv/gconv-modules* /usr/lib/gconv/ISO8859* /usr/lib/gconv/UTF* "${GLIBC_DEST}/usr/lib/gconv/" 2>/dev/null || true

cat << 'EOF' > "${WORK_DIR}/recipe-glibc.toml"
[package]
name = "glibc"
version = "2.39"
release = 1
architecture = "x86_64"
summary = "GNU C Library"
description = "Core C runtime, dynamic linker, NSS modules and localization for BlazeOS Native."
license = "LGPL-2.1-or-later"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://www.gnu.org/software/libc/"

[dependencies]
provides = [
    "glibc = 2.39",
    "lib:libc.so.6",
    "lib:libm.so.6",
    "lib:libdl.so.2",
    "lib:libpthread.so.0",
    "lib:librt.so.1",
    "lib:libcrypt.so.1",
    "lib:libcrypt.so.2",
    "lib:libnss_files.so.2",
    "lib:libnss_dns.so.2",
    "lib:ld-linux-x86-64.so.2",
    "cmd:ldconfig"
]

[triggers]
run_ldconfig = true

[build]
script = """
cp -a "$CURRENT_DIR/build/seed_work/glibc-dest/"* "$DESTDIR/"
"""
EOF

"${BUILDER}" "${WORK_DIR}/recipe-glibc.toml"

is_glibc_lib() {
    local base="$(basename "$1")"
    case "$base" in
        libc.*|libc-*|libm.*|libm-*|libdl.*|libdl-*|libpthread.*|libpthread-*|librt.*|librt-*|libutil.*|libutil-*|libresolv.*|libresolv-*|libcrypt.*|libcrypt-*|libnss_*|ld-linux*|libgcc_s*|libcrypto*|libcryptsetup*)
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

# 3. Package bash
BASH_DEST="${WORK_DIR}/bash-dest"
rm -rf "${BASH_DEST}"
mkdir -p "${BASH_DEST}/usr/bin" "${BASH_DEST}/usr/lib"

echo "Collecting Bash..."
cp -a /usr/bin/bash "${BASH_DEST}/usr/bin/bash"
ln -sf bash "${BASH_DEST}/usr/bin/sh"

# Copy readline/ncurses shared libs needed by bash if not in glibc
for lib in $(ldd /usr/bin/bash | grep '=> /' | awk '{print $3}'); do
    if [ -f "$lib" ] && ! is_glibc_lib "$lib"; then
        cp -a "$lib"* "${BASH_DEST}/usr/lib/" 2>/dev/null || true
    fi
done

cat << 'EOF' > "${WORK_DIR}/recipe-bash.toml"
[package]
name = "bash"
version = "5.2.21"
release = 1
architecture = "x86_64"
summary = "The GNU Bourne-Again SHell"
description = "Primary shell for BlazeOS Native."
license = "GPL-3.0-or-later"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://www.gnu.org/software/bash/"

[dependencies]
requires = ["glibc >= 2.38"]
provides = [
    "bash = 5.2.21",
    "cmd:bash",
    "cmd:sh",
    "sh = 5.2.21"
]

[build]
script = """
cp -a "$CURRENT_DIR/build/seed_work/bash-dest/"* "$DESTDIR/"
"""
EOF

"${BUILDER}" "${WORK_DIR}/recipe-bash.toml"

# 4. Package coreutils
COREUTILS_DEST="${WORK_DIR}/coreutils-dest"
rm -rf "${COREUTILS_DEST}"
mkdir -p "${COREUTILS_DEST}/usr/bin"

echo "Collecting Coreutils binaries..."
CORE_BINS=(cat ls cp mv rm mkdir rmdir chmod chown chgrp uname date env touch head tail cut sort uniq grep sed awk)

for bin in "${CORE_BINS[@]}"; do
    bin_path="/usr/bin/${bin}"
    if [ -f "${bin_path}" ]; then
        cp -a "${bin_path}" "${COREUTILS_DEST}/usr/bin/"
    fi
done

cat << 'EOF' > "${WORK_DIR}/recipe-coreutils.toml"
[package]
name = "coreutils"
version = "9.4"
release = 1
architecture = "x86_64"
summary = "The GNU Core Utilities"
description = "Essential core utilities for BlazeOS Native."
license = "GPL-3.0-or-later"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://www.gnu.org/software/coreutils/"

[dependencies]
requires = ["glibc >= 2.38"]
provides = [
    "coreutils = 9.4",
    "cmd:cat",
    "cmd:ls",
    "cmd:cp",
    "cmd:mv",
    "cmd:rm",
    "cmd:mkdir"
]

[build]
script = """
cp -a "$CURRENT_DIR/build/seed_work/coreutils-dest/"* "$DESTDIR/"
"""
EOF

"${BUILDER}" "${WORK_DIR}/recipe-coreutils.toml"

echo "=== All Milestone 1 .blz Packages Successfully Generated in ${PKGS_DIR} ==="
ls -lh "${PKGS_DIR}"/*.blz
