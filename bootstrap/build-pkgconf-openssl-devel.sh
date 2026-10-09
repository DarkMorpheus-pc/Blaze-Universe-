#!/usr/bin/env bash
set -euo pipefail

BLAZE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK_DIR="${BLAZE_ROOT}/build/pkgconf_openssl_work"
PKGS_DIR="${BLAZE_ROOT}/build/packages"
BUILDER="${BLAZE_ROOT}/target/debug/blaze-builder"

mkdir -p "${WORK_DIR}" "${PKGS_DIR}"

# 1. Package pkgconf
PKGCONF_DEST="${WORK_DIR}/pkgconf-dest"
rm -rf "${PKGCONF_DEST}"
mkdir -p "${PKGCONF_DEST}/usr/bin" "${PKGCONF_DEST}/usr/lib/pkgconfig" "${PKGCONF_DEST}/usr/include/pkgconf"

cp -a /usr/bin/pkgconf "${PKGCONF_DEST}/usr/bin/"
ln -sf pkgconf "${PKGCONF_DEST}/usr/bin/pkg-config"
ln -sf pkgconf "${PKGCONF_DEST}/usr/bin/x86_64-pc-linux-gnu-pkg-config"
ln -sf pkgconf "${PKGCONF_DEST}/usr/bin/x86_64-linux-gnu-pkg-config"

cp -a /usr/lib/libpkgconf.so* "${PKGCONF_DEST}/usr/lib/"
cp -a /usr/lib/pkgconfig/libpkgconf.pc "${PKGCONF_DEST}/usr/lib/pkgconfig/"
cp -a /usr/include/pkgconf/* "${PKGCONF_DEST}/usr/include/pkgconf/" 2>/dev/null || true

cat << 'ENDTOML' > "${WORK_DIR}/recipe-pkgconf.toml"
[package]
name = "pkgconf"
version = "3.0.7"
release = 1
architecture = "x86_64"
summary = "Package compiler and linker metadata toolkit"
description = "pkgconf is a program which helps to configure compiler and linker flags for development libraries."
license = "ISC"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "http://pkgconf.org/"

[dependencies]
requires = ["glibc = 2.44"]
provides = [
    "pkgconf = 3.0.7",
    "cmd:pkgconf",
    "cmd:pkg-config",
    "lib:libpkgconf.so.8"
]

[triggers]
run_ldconfig = true

[build]
script = """
cp -a "$CURRENT_DIR/build/pkgconf_openssl_work/pkgconf-dest/"* "$DESTDIR/"
"""
ENDTOML

"${BUILDER}" "${WORK_DIR}/recipe-pkgconf.toml" --output-dir "${PKGS_DIR}"

# 2. Package openssl-devel
OPENSSL_DEST="${WORK_DIR}/openssl-devel-dest"
rm -rf "${OPENSSL_DEST}"
mkdir -p "${OPENSSL_DEST}/usr/include" "${OPENSSL_DEST}/usr/lib/pkgconfig"

cp -a /usr/include/openssl "${OPENSSL_DEST}/usr/include/"
cp -a /usr/lib/pkgconfig/openssl.pc "${OPENSSL_DEST}/usr/lib/pkgconfig/"
cp -a /usr/lib/pkgconfig/libssl.pc "${OPENSSL_DEST}/usr/lib/pkgconfig/"
cp -a /usr/lib/pkgconfig/libcrypto.pc "${OPENSSL_DEST}/usr/lib/pkgconfig/"

cat << 'ENDTOML' > "${WORK_DIR}/recipe-openssl-devel.toml"
[package]
name = "openssl-devel"
version = "3.6.4"
release = 1
architecture = "x86_64"
summary = "Headers and pkgconfig metadata for OpenSSL"
description = "Development files for OpenSSL cryptography and TLS library."
license = "Apache-2.0"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://www.openssl.org/"

[dependencies]
requires = ["glibc = 2.44"]
provides = [
    "openssl-devel = 3.6.4"
]

[build]
script = """
cp -a "$CURRENT_DIR/build/pkgconf_openssl_work/openssl-devel-dest/"* "$DESTDIR/"
"""
ENDTOML

"${BUILDER}" "${WORK_DIR}/recipe-openssl-devel.toml" --output-dir "${PKGS_DIR}"

echo "=== Packaging Complete ==="
ls -lh "${PKGS_DIR}"/pkgconf-*.blz "${PKGS_DIR}"/openssl-devel-*.blz
