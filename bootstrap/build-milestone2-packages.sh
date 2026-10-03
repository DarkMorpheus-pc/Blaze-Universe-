#!/usr/bin/env bash
# ==============================================================================
# Blaze Universe — Milestone 2 System Packages Builder
# ==============================================================================
# Builds all foundational system libraries and service orchestration components:
#   zlib, xz, zstd, openssl, libcap, libseccomp, util-linux, kmod, shadow, pam, dbus, systemd
# strictly conforming to UsrMerge and Declarative BLZ v0.1 format.
# ==============================================================================

set -euo pipefail

BLAZE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK_DIR="${BLAZE_ROOT}/build/m2_work"
PKGS_DIR="${BLAZE_ROOT}/build/packages"
BUILDER="${BLAZE_ROOT}/target/debug/blaze-builder"

mkdir -p "${WORK_DIR}" "${PKGS_DIR}"

echo "=== Building Milestone 2 Core Packages ==="

# Helper to pack a component
build_component() {
    local name="$1"
    local version="$2"
    local dest="$3"
    local recipe_path="$4"
    echo "--- Building ${name} (${version}) ---"
    "${BUILDER}" "${recipe_path}"
}

# 0a. libattr
ATTR_DEST="${WORK_DIR}/libattr-dest"
rm -rf "${ATTR_DEST}"
mkdir -p "${ATTR_DEST}/usr/lib"
cp -a /usr/lib/libattr.so* "${ATTR_DEST}/usr/lib/"

cat << 'EOF' > "${BLAZE_ROOT}/recipes/core/libattr/recipe.toml"
[package]
name = "libattr"
version = "2.5.2"
release = 1
architecture = "x86_64"
summary = "Extended attributes library"
license = "LGPL-2.1-or-later"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://savannah.nongnu.org/projects/attr"

[dependencies]
provides = ["libattr = 2.5.2", "lib:libattr.so.1"]

[build]
script = """
cp -a "$CURRENT_DIR/build/m2_work/libattr-dest/"* "$DESTDIR/"
"""
EOF
build_component "libattr" "2.5.2" "${ATTR_DEST}" "${BLAZE_ROOT}/recipes/core/libattr/recipe.toml"

# 0b. libacl
ACL_DEST="${WORK_DIR}/libacl-dest"
rm -rf "${ACL_DEST}"
mkdir -p "${ACL_DEST}/usr/lib"
cp -a /usr/lib/libacl.so* "${ACL_DEST}/usr/lib/"

cat << 'EOF' > "${BLAZE_ROOT}/recipes/core/libacl/recipe.toml"
[package]
name = "libacl"
version = "2.3.2"
release = 1
architecture = "x86_64"
summary = "Access Control List library"
license = "LGPL-2.1-or-later"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://savannah.nongnu.org/projects/acl"

[dependencies]
provides = ["libacl = 2.3.2", "lib:libacl.so.1"]

[build]
script = """
cp -a "$CURRENT_DIR/build/m2_work/libacl-dest/"* "$DESTDIR/"
"""
EOF
build_component "libacl" "2.3.2" "${ACL_DEST}" "${BLAZE_ROOT}/recipes/core/libacl/recipe.toml"

# 0c. gmp
GMP_DEST="${WORK_DIR}/gmp-dest"
rm -rf "${GMP_DEST}"
mkdir -p "${GMP_DEST}/usr/lib"
cp -a /usr/lib/libgmp.so* "${GMP_DEST}/usr/lib/"

cat << 'EOF' > "${BLAZE_ROOT}/recipes/core/gmp/recipe.toml"
[package]
name = "gmp"
version = "6.3.0"
release = 1
architecture = "x86_64"
summary = "GNU Multiple Precision Arithmetic Library"
license = "LGPL-3.0-or-later"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://gmplib.org/"

[dependencies]
provides = ["gmp = 6.3.0", "lib:libgmp.so.10"]

[build]
script = """
cp -a "$CURRENT_DIR/build/m2_work/gmp-dest/"* "$DESTDIR/"
"""
EOF
build_component "gmp" "6.3.0" "${GMP_DEST}" "${BLAZE_ROOT}/recipes/core/gmp/recipe.toml"

# 0d. mpfr
MPFR_DEST="${WORK_DIR}/mpfr-dest"
rm -rf "${MPFR_DEST}"
mkdir -p "${MPFR_DEST}/usr/lib"
cp -a /usr/lib/libmpfr.so* "${MPFR_DEST}/usr/lib/"

cat << 'EOF' > "${BLAZE_ROOT}/recipes/core/mpfr/recipe.toml"
[package]
name = "mpfr"
version = "4.2.1"
release = 1
architecture = "x86_64"
summary = "Multiple-precision floating-point computations library"
license = "LGPL-3.0-or-later"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://www.mpfr.org/"

[dependencies]
provides = ["mpfr = 4.2.1", "lib:libmpfr.so.6"]

[build]
script = """
cp -a "$CURRENT_DIR/build/m2_work/mpfr-dest/"* "$DESTDIR/"
"""
EOF
build_component "mpfr" "4.2.1" "${MPFR_DEST}" "${BLAZE_ROOT}/recipes/core/mpfr/recipe.toml"

# 0e. pcre2
PCRE_DEST="${WORK_DIR}/pcre2-dest"
rm -rf "${PCRE_DEST}"
mkdir -p "${PCRE_DEST}/usr/lib"
cp -a /usr/lib/libpcre2-8.so* "${PCRE_DEST}/usr/lib/"

cat << 'EOF' > "${BLAZE_ROOT}/recipes/core/pcre2/recipe.toml"
[package]
name = "pcre2"
version = "10.44"
release = 1
architecture = "x86_64"
summary = "Perl Compatible Regular Expressions library"
license = "BSD-3-Clause"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://www.pcre.org/"

[dependencies]
provides = ["pcre2 = 10.44", "lib:libpcre2-8.so.0"]

[build]
script = """
cp -a "$CURRENT_DIR/build/m2_work/pcre2-dest/"* "$DESTDIR/"
"""
EOF
build_component "pcre2" "10.44" "${PCRE_DEST}" "${BLAZE_ROOT}/recipes/core/pcre2/recipe.toml"

# 1. zlib
ZLIB_DEST="${WORK_DIR}/zlib-dest"
rm -rf "${ZLIB_DEST}"
mkdir -p "${ZLIB_DEST}/usr/lib"
cp -a /usr/lib/libz.so* "${ZLIB_DEST}/usr/lib/"

cat << 'EOF' > "${BLAZE_ROOT}/recipes/core/zlib/recipe.toml"
[package]
name = "zlib"
version = "1.3.1"
release = 1
architecture = "x86_64"
summary = "Compression and decompression library"
license = "Zlib"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://zlib.net/"

[dependencies]
provides = ["zlib = 1.3.1", "lib:libz.so.1"]

[build]
script = """
cp -a "$CURRENT_DIR/build/m2_work/zlib-dest/"* "$DESTDIR/"
"""
EOF
build_component "zlib" "1.3.1" "${ZLIB_DEST}" "${BLAZE_ROOT}/recipes/core/zlib/recipe.toml"

# 2. xz
XZ_DEST="${WORK_DIR}/xz-dest"
rm -rf "${XZ_DEST}"
mkdir -p "${XZ_DEST}/usr/lib" "${XZ_DEST}/usr/bin"
cp -a /usr/lib/liblzma.so* "${XZ_DEST}/usr/lib/"
cp -a /usr/bin/xz /usr/bin/lzma /usr/bin/unxz "${XZ_DEST}/usr/bin/" 2>/dev/null || true

cat << 'EOF' > "${BLAZE_ROOT}/recipes/core/xz/recipe.toml"
[package]
name = "xz"
version = "5.6.2"
release = 1
architecture = "x86_64"
summary = "Library and command line tools for XZ and LZMA compressed files"
license = "GPL-2.0-or-later AND LGPL-2.1-or-later"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://tukaani.org/xz/"

[dependencies]
provides = ["xz = 5.6.2", "lib:liblzma.so.5", "cmd:xz"]

[build]
script = """
cp -a "$CURRENT_DIR/build/m2_work/xz-dest/"* "$DESTDIR/"
"""
EOF
build_component "xz" "5.6.2" "${XZ_DEST}" "${BLAZE_ROOT}/recipes/core/xz/recipe.toml"

# 3. zstd
ZSTD_DEST="${WORK_DIR}/zstd-dest"
rm -rf "${ZSTD_DEST}"
mkdir -p "${ZSTD_DEST}/usr/lib" "${ZSTD_DEST}/usr/bin"
cp -a /usr/lib/libzstd.so* "${ZSTD_DEST}/usr/lib/"
cp -a /usr/lib/liblz4.so* "${ZSTD_DEST}/usr/lib/"
cp -a /usr/bin/zstd /usr/bin/zstdcat /usr/bin/unzstd "${ZSTD_DEST}/usr/bin/" 2>/dev/null || true

cat << 'EOF' > "${BLAZE_ROOT}/recipes/core/zstd/recipe.toml"
[package]
name = "zstd"
version = "1.5.6"
release = 1
architecture = "x86_64"
summary = "Zstandard - Fast real-time compression algorithm"
license = "BSD-3-Clause OR GPL-2.0-only"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://facebook.github.io/zstd/"

[dependencies]
provides = ["zstd = 1.5.6", "lib:libzstd.so.1", "cmd:zstd"]

[build]
script = """
cp -a "$CURRENT_DIR/build/m2_work/zstd-dest/"* "$DESTDIR/"
"""
EOF
build_component "zstd" "1.5.6" "${ZSTD_DEST}" "${BLAZE_ROOT}/recipes/core/zstd/recipe.toml"

# 4. openssl
OPENSSL_DEST="${WORK_DIR}/openssl-dest"
rm -rf "${OPENSSL_DEST}"
mkdir -p "${OPENSSL_DEST}/usr/lib" "${OPENSSL_DEST}/usr/bin" "${OPENSSL_DEST}/etc/ssl"
cp -a /usr/lib/libssl.so* /usr/lib/libcrypto.so* "${OPENSSL_DEST}/usr/lib/"
cp -a /usr/bin/openssl "${OPENSSL_DEST}/usr/bin/"
[ -d /etc/ssl ] && cp -a /etc/ssl/* "${OPENSSL_DEST}/etc/ssl/" 2>/dev/null || true

cat << 'EOF' > "${BLAZE_ROOT}/recipes/core/openssl/recipe.toml"
[package]
name = "openssl"
version = "3.3.1"
release = 1
architecture = "x86_64"
summary = "Cryptography and SSL/TLS Toolkit"
license = "Apache-2.0"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://www.openssl.org/"

[dependencies]
provides = ["openssl = 3.3.1", "lib:libssl.so.3", "lib:libcrypto.so.3", "cmd:openssl"]

[build]
script = """
cp -a "$CURRENT_DIR/build/m2_work/openssl-dest/"* "$DESTDIR/"
"""
EOF
build_component "openssl" "3.3.1" "${OPENSSL_DEST}" "${BLAZE_ROOT}/recipes/core/openssl/recipe.toml"

# 5. libcap
LIBCAP_DEST="${WORK_DIR}/libcap-dest"
rm -rf "${LIBCAP_DEST}"
mkdir -p "${LIBCAP_DEST}/usr/lib" "${LIBCAP_DEST}/usr/bin"
cp -a /usr/lib/libcap.so* "${LIBCAP_DEST}/usr/lib/"
cp -a /usr/bin/capsh /usr/bin/getcap /usr/bin/setcap "${LIBCAP_DEST}/usr/bin/" 2>/dev/null || true

cat << 'EOF' > "${BLAZE_ROOT}/recipes/core/libcap/recipe.toml"
[package]
name = "libcap"
version = "2.70"
release = 1
architecture = "x86_64"
summary = "POSIX 1003.1e capabilities library"
license = "GPL-2.0-only OR BSD-3-Clause"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://sites.google.com/site/fullycapable/"

[dependencies]
provides = ["libcap = 2.70", "lib:libcap.so.2", "cmd:capsh"]

[build]
script = """
cp -a "$CURRENT_DIR/build/m2_work/libcap-dest/"* "$DESTDIR/"
"""
EOF
build_component "libcap" "2.70" "${LIBCAP_DEST}" "${BLAZE_ROOT}/recipes/core/libcap/recipe.toml"

# 6. libseccomp
LIBSECCOMP_DEST="${WORK_DIR}/libseccomp-dest"
rm -rf "${LIBSECCOMP_DEST}"
mkdir -p "${LIBSECCOMP_DEST}/usr/lib"
cp -a /usr/lib/libseccomp.so* "${LIBSECCOMP_DEST}/usr/lib/"

cat << 'EOF' > "${BLAZE_ROOT}/recipes/core/libseccomp/recipe.toml"
[package]
name = "libseccomp"
version = "2.5.5"
release = 1
architecture = "x86_64"
summary = "Enhanced seccomp library and kernel abstraction layer"
license = "LGPL-2.1-only"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://github.com/seccomp/libseccomp"

[dependencies]
provides = ["libseccomp = 2.5.5", "lib:libseccomp.so.2"]

[build]
script = """
cp -a "$CURRENT_DIR/build/m2_work/libseccomp-dest/"* "$DESTDIR/"
"""
EOF
build_component "libseccomp" "2.5.5" "${LIBSECCOMP_DEST}" "${BLAZE_ROOT}/recipes/core/libseccomp/recipe.toml"

# 7. util-linux
UTIL_DEST="${WORK_DIR}/util-linux-dest"
rm -rf "${UTIL_DEST}"
mkdir -p "${UTIL_DEST}/usr/lib" "${UTIL_DEST}/usr/bin"
cp -a /usr/lib/libmount.so* /usr/lib/libblkid.so* /usr/lib/libuuid.so* /usr/lib/libsmartcols.so* /usr/lib/libfdisk.so* "${UTIL_DEST}/usr/lib/"
for b in agetty mount umount blkid findmnt lsblk fdisk sfdisk swapon swapoff dmesg fallocate setsid sulogin; do
    if [ -f "/usr/bin/$b" ]; then
        cp -a "/usr/bin/$b" "${UTIL_DEST}/usr/bin/"
    fi
done

cat << 'EOF' > "${BLAZE_ROOT}/recipes/core/util-linux/recipe.toml"
[package]
name = "util-linux"
version = "2.40.1"
release = 1
architecture = "x86_64"
summary = "Miscellaneous system utilities for Linux"
license = "GPL-2.0-only AND LGPL-2.1-or-later AND BSD-4-Clause-UC"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://github.com/util-linux/util-linux"

[dependencies]
provides = [
    "util-linux = 2.40.1",
    "lib:libmount.so.1",
    "lib:libblkid.so.1",
    "lib:libuuid.so.1",
    "lib:libsmartcols.so.1",
    "lib:libfdisk.so.1",
    "cmd:agetty",
    "cmd:mount",
    "cmd:umount",
    "cmd:blkid"
]

[build]
script = """
cp -a "$CURRENT_DIR/build/m2_work/util-linux-dest/"* "$DESTDIR/"
"""
EOF
build_component "util-linux" "2.40.1" "${UTIL_DEST}" "${BLAZE_ROOT}/recipes/core/util-linux/recipe.toml"

# 8. kmod
KMOD_DEST="${WORK_DIR}/kmod-dest"
rm -rf "${KMOD_DEST}"
mkdir -p "${KMOD_DEST}/usr/lib" "${KMOD_DEST}/usr/bin"
cp -a /usr/lib/libkmod.so* "${KMOD_DEST}/usr/lib/"
cp -a /usr/lib/libbrotli*.so* "${KMOD_DEST}/usr/lib/" 2>/dev/null || true
cp -a /usr/bin/kmod "${KMOD_DEST}/usr/bin/"
for b in lsmod modprobe insmod rmmod modinfo depmod; do
    ln -sf kmod "${KMOD_DEST}/usr/bin/$b"
done

cat << 'EOF' > "${BLAZE_ROOT}/recipes/core/kmod/recipe.toml"
[package]
name = "kmod"
version = "32"
release = 1
architecture = "x86_64"
summary = "Linux kernel module management tools and library"
license = "LGPL-2.1-or-later AND GPL-2.0-or-later"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://git.kernel.org/pub/scm/utils/kernel/kmod/kmod.git"

[dependencies]
provides = [
    "kmod = 32",
    "lib:libkmod.so.2",
    "cmd:kmod",
    "cmd:modprobe",
    "cmd:lsmod"
]

[build]
script = """
cp -a "$CURRENT_DIR/build/m2_work/kmod-dest/"* "$DESTDIR/"
"""
EOF
build_component "kmod" "32" "${KMOD_DEST}" "${BLAZE_ROOT}/recipes/core/kmod/recipe.toml"

# 9. shadow
SHADOW_DEST="${WORK_DIR}/shadow-dest"
rm -rf "${SHADOW_DEST}"
mkdir -p "${SHADOW_DEST}/usr/bin" "${SHADOW_DEST}/usr/lib" "${SHADOW_DEST}/etc"
cp -a /usr/lib/libaudit.so* /usr/lib/libcap-ng.so* "${SHADOW_DEST}/usr/lib/" 2>/dev/null || true
for b in login passwd useradd userdel usermod groupadd groupdel su chpasswd; do
    if [ -f "/usr/bin/$b" ]; then
        cp -a "/usr/bin/$b" "${SHADOW_DEST}/usr/bin/"
    fi
done
cp -a /etc/login.defs "${SHADOW_DEST}/etc/" 2>/dev/null || true

cat << 'EOF' > "${BLAZE_ROOT}/recipes/core/shadow/recipe.toml"
[package]
name = "shadow"
version = "4.15.1"
release = 1
architecture = "x86_64"
summary = "Password and account management tool suite"
license = "BSD-3-Clause"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://github.com/shadow-maint/shadow"

[dependencies]
provides = [
    "shadow = 4.15.1",
    "cmd:login",
    "cmd:passwd",
    "cmd:useradd",
    "cmd:su"
]

[build]
script = """
cp -a "$CURRENT_DIR/build/m2_work/shadow-dest/"* "$DESTDIR/"
"""
EOF
build_component "shadow" "4.15.1" "${SHADOW_DEST}" "${BLAZE_ROOT}/recipes/core/shadow/recipe.toml"

# 10. pam (Linux-PAM)
PAM_DEST="${WORK_DIR}/pam-dest"
rm -rf "${PAM_DEST}"
mkdir -p "${PAM_DEST}/usr/lib" "${PAM_DEST}/usr/lib/security" "${PAM_DEST}/etc/pam.d"
cp -a /usr/lib/libpam.so* /usr/lib/libpam_misc.so* /usr/lib/libpamc.so* "${PAM_DEST}/usr/lib/"
cp -a /usr/lib/libtirpc.so* /usr/lib/libnsl.so* /usr/lib/libkeyutils.so* /usr/lib/liblastlog2.so* /usr/lib/libgssapi_krb5.so* /usr/lib/libkrb5.so* /usr/lib/libk5crypto.so* /usr/lib/libcom_err.so* /usr/lib/libkrb5support.so* "${PAM_DEST}/usr/lib/" 2>/dev/null || true
cp -a /usr/lib/security/*.so "${PAM_DEST}/usr/lib/security/" 2>/dev/null || true

# Standard minimal PAM configuration that allows root login
cat << 'EOF' > "${PAM_DEST}/etc/pam.d/other"
auth     required pam_unix.so nullok
account  required pam_unix.so
password required pam_unix.so nullok sha512 shadow
session  required pam_unix.so
EOF

for s in login su system-auth passwd; do
    cp -a "${PAM_DEST}/etc/pam.d/other" "${PAM_DEST}/etc/pam.d/$s"
done

cat << 'EOF' > "${BLAZE_ROOT}/recipes/core/pam/recipe.toml"
[package]
name = "pam"
version = "1.6.1"
release = 1
architecture = "x86_64"
summary = "Pluggable Authentication Modules for Linux"
license = "BSD-3-Clause OR GPL-2.0-only"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://github.com/linux-pam/linux-pam"

[dependencies]
provides = [
    "pam = 1.6.1",
    "lib:libpam.so.0",
    "lib:libpam_misc.so.0",
    "lib:libpamc.so.0"
]

[build]
script = """
cp -a "$CURRENT_DIR/build/m2_work/pam-dest/"* "$DESTDIR/"
"""
EOF
build_component "pam" "1.6.1" "${PAM_DEST}" "${BLAZE_ROOT}/recipes/core/pam/recipe.toml"

# 11. dbus
DBUS_DEST="${WORK_DIR}/dbus-dest"
rm -rf "${DBUS_DEST}"
mkdir -p "${DBUS_DEST}/usr/lib" "${DBUS_DEST}/usr/bin" "${DBUS_DEST}/usr/lib/sysusers.d" "${DBUS_DEST}/usr/lib/systemd/system" "${DBUS_DEST}/usr/share/dbus-1"
cp -a /usr/lib/libdbus-1.so* /usr/lib/libexpat.so* "${DBUS_DEST}/usr/lib/"
cp -a /usr/bin/dbus-daemon /usr/bin/dbus-send /usr/bin/dbus-launch "${DBUS_DEST}/usr/bin/" 2>/dev/null || true
cat << 'UNIT_EOF' > "${DBUS_DEST}/usr/lib/systemd/system/dbus.service"
[Unit]
Description=D-Bus System Message Bus
Documentation=man:dbus-daemon(1)
DefaultDependencies=no
After=dbus.socket
Before=basic.target shutdown.target
Requires=dbus.socket
Conflicts=shutdown.target

[Service]
ExecStart=/usr/bin/dbus-daemon --system --address=systemd: --nofork --nopidfile --systemd-activation --syslog-only
ExecReload=/usr/bin/dbus-send --print-reply --system --type=method_call --dest=org.freedesktop.DBus / org.freedesktop.DBus.ReloadConfig
OOMScoreAdjust=-900

[Install]
WantedBy=multi-user.target
UNIT_EOF

cat << 'UNIT_EOF' > "${DBUS_DEST}/usr/lib/systemd/system/dbus.socket"
[Unit]
Description=D-Bus System Message Bus Socket
Documentation=man:dbus-daemon(1)

[Socket]
ListenStream=/run/dbus/system_bus_socket
UNIT_EOF

cat << 'EOF' > "${BLAZE_ROOT}/recipes/core/dbus/recipe.toml"
[package]
name = "dbus"
version = "1.14.10"
release = 1
architecture = "x86_64"
summary = "Freedesktop.org message bus system"
license = "AFL-2.1 OR GPL-2.0-or-later"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://www.freedesktop.org/wiki/Software/dbus/"

[dependencies]
provides = ["dbus = 1.14.10", "lib:libdbus-1.so.3", "cmd:dbus-daemon"]

[sysusers]
files = ["usr/lib/sysusers.d/dbus.conf"]

[services]
preset = ["dbus.service"]

[build]
script = """
cp -a "$CURRENT_DIR/build/m2_work/dbus-dest/"* "$DESTDIR/"
"""
EOF
build_component "dbus" "1.14.10" "${DBUS_DEST}" "${BLAZE_ROOT}/recipes/core/dbus/recipe.toml"

# 12. systemd
SYSTEMD_DEST="${WORK_DIR}/systemd-dest"
rm -rf "${SYSTEMD_DEST}"
mkdir -p "${SYSTEMD_DEST}/usr/lib/systemd/system" "${SYSTEMD_DEST}/usr/bin" "${SYSTEMD_DEST}/usr/lib" "${SYSTEMD_DEST}/usr/lib/sysusers.d" "${SYSTEMD_DEST}/usr/lib/tmpfiles.d"

echo "Collecting systemd components..."
# Core init & systemctl
cp -a /usr/lib/systemd/systemd "${SYSTEMD_DEST}/usr/lib/systemd/"
ln -sf usr/lib/systemd/systemd "${SYSTEMD_DEST}/init" 2>/dev/null || true
mkdir -p "${SYSTEMD_DEST}/usr/sbin"
ln -sf ../lib/systemd/systemd "${SYSTEMD_DEST}/usr/sbin/init" 2>/dev/null || true

cp -a /usr/bin/systemctl /usr/bin/journalctl /usr/bin/udevadm /usr/bin/systemd-sysusers /usr/bin/systemd-tmpfiles "${SYSTEMD_DEST}/usr/bin/"
[ -f /usr/lib/systemd/systemd-udevd ] && cp -a /usr/lib/systemd/systemd-udevd "${SYSTEMD_DEST}/usr/lib/systemd/" || true
[ -f /usr/lib/systemd/systemd-journald ] && cp -a /usr/lib/systemd/systemd-journald "${SYSTEMD_DEST}/usr/lib/systemd/" || true
[ -f /usr/lib/systemd/systemd-logind ] && cp -a /usr/lib/systemd/systemd-logind "${SYSTEMD_DEST}/usr/lib/systemd/" || true

# Systemd helpers & executors
cp -a /usr/lib/systemd/systemd-* "${SYSTEMD_DEST}/usr/lib/systemd/" 2>/dev/null || true

# Systemd shared libraries & BPF
cp -a /usr/lib/libsystemd.so* /usr/lib/libudev.so* "${SYSTEMD_DEST}/usr/lib/"
cp -a /usr/lib/systemd/*.so* "${SYSTEMD_DEST}/usr/lib/systemd/"
cp -a /usr/lib/libbpf.so* /usr/lib/libelf.so* "${SYSTEMD_DEST}/usr/lib/" 2>/dev/null || true

# System generators
mkdir -p "${SYSTEMD_DEST}/usr/lib/systemd/system-generators"
cp -a /usr/lib/systemd/system-generators/systemd-fstab-generator /usr/lib/systemd/system-generators/systemd-getty-generator "${SYSTEMD_DEST}/usr/lib/systemd/system-generators/" 2>/dev/null || true

# Udev rules and helpers
mkdir -p "${SYSTEMD_DEST}/usr/lib/udev/rules.d"
cp -a /usr/lib/udev/* "${SYSTEMD_DEST}/usr/lib/udev/" 2>/dev/null || true

# Basic units
for u in basic.target multi-user.target graphical.target rescue.target emergency.target shutdown.target reboot.target poweroff.target local-fs.target remote-fs.target sysinit.target sockets.target timers.target paths.target getty@.service getty.target systemd-journald.service systemd-udevd.service systemd-logind.service systemd-sysusers.service systemd-tmpfiles-setup.service systemd-tmpfiles-setup-dev.service console-getty.service; do
    [ -f "/usr/lib/systemd/system/$u" ] && cp -a "/usr/lib/systemd/system/$u" "${SYSTEMD_DEST}/usr/lib/systemd/system/" || true
done


# Default target symlink (default.target -> multi-user.target)
ln -sf multi-user.target "${SYSTEMD_DEST}/usr/lib/systemd/system/default.target"

# getty & console-getty enablement
mkdir -p "${SYSTEMD_DEST}/usr/lib/systemd/system/getty.target.wants"
mkdir -p "${SYSTEMD_DEST}/usr/lib/systemd/system/multi-user.target.wants"
ln -sf ../getty.target "${SYSTEMD_DEST}/usr/lib/systemd/system/multi-user.target.wants/getty.target"
ln -sf ../getty@.service "${SYSTEMD_DEST}/usr/lib/systemd/system/getty.target.wants/getty@tty1.service"
ln -sf ../getty@.service "${SYSTEMD_DEST}/usr/lib/systemd/system/getty.target.wants/getty@ttyS0.service"
ln -sf ../console-getty.service "${SYSTEMD_DEST}/usr/lib/systemd/system/getty.target.wants/console-getty.service"

# Sysusers & tmpfiles
cp -a /usr/lib/sysusers.d/basic.conf /usr/lib/sysusers.d/systemd.conf "${SYSTEMD_DEST}/usr/lib/sysusers.d/" 2>/dev/null || true
cp -a /usr/lib/tmpfiles.d/systemd.conf /usr/lib/tmpfiles.d/tmp.conf "${SYSTEMD_DEST}/usr/lib/tmpfiles.d/" 2>/dev/null || true

cat << 'EOF' > "${BLAZE_ROOT}/recipes/core/systemd/recipe.toml"
[package]
name = "systemd"
version = "255"
release = 1
architecture = "x86_64"
summary = "System and Service Manager for BlazeOS Native"
license = "LGPL-2.1-or-later"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://systemd.io/"

[dependencies]
provides = [
    "systemd = 255",
    "init",
    "lib:libsystemd.so.0",
    "lib:libudev.so.1",
    "cmd:systemctl",
    "cmd:journalctl",
    "cmd:udevadm"
]

[sysusers]
files = ["usr/lib/sysusers.d/basic.conf", "usr/lib/sysusers.d/systemd.conf"]

[tmpfiles]
files = ["usr/lib/tmpfiles.d/systemd.conf", "usr/lib/tmpfiles.d/tmp.conf"]

[services]
preset = [
    "systemd-journald.service",
    "systemd-udevd.service",
    "systemd-logind.service",
    "getty@tty1.service",
    "getty@ttyS0.service"
]

[build]
script = """
cp -a "$CURRENT_DIR/build/m2_work/systemd-dest/"* "$DESTDIR/"
"""
EOF
build_component "systemd" "255" "${SYSTEMD_DEST}" "${BLAZE_ROOT}/recipes/core/systemd/recipe.toml"

echo "=== All 12 Milestone 2 Packages Successfully Generated in ${PKGS_DIR} ==="
ls -lh "${PKGS_DIR}"/*.blz
