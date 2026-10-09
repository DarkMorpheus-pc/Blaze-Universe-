#!/usr/bin/env bash
# ==============================================================================
# Blaze Universe — Auxiliary Build Tools Package Generator (Stage 3.1)
# ==============================================================================
# Assembles clean, UsrMerged, standalone .blz packages for:
#   - bzip2 (1.0.8) [provides libbz2.so.1.0]
#   - tar (1.35)
#   - gzip (1.15)
#   - diffutils (3.12)
#   - patch (2.8)
#   - findutils (4.11.0)
#   - grep (3.12)
#   - sed (4.10)
#   - gawk (5.4.1)
#   - which (2.21)
#   - m4 (1.4.21)
#   - blaze-builder (0.1.0)
# All packaged strictly through Portadora .blz format without host contamination.
# ==============================================================================

set -euo pipefail

BLAZE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK_DIR="${BLAZE_ROOT}/build/aux_work"
PKGS_DIR="${BLAZE_ROOT}/build/packages"
BUILDER="${BLAZE_ROOT}/target/debug/blaze-builder"

mkdir -p "${WORK_DIR}" "${PKGS_DIR}"

echo "=== Building Stage 3.1 Auxiliary Development Tools Packages ==="

# 1. bzip2
BZIP2_DEST="${WORK_DIR}/bzip2-dest"
rm -rf "${BZIP2_DEST}"
mkdir -p "${BZIP2_DEST}/usr/bin" "${BZIP2_DEST}/usr/lib" "${BZIP2_DEST}/usr/include"
cp -a /usr/bin/bzip2 /usr/bin/bunzip2 /usr/bin/bzcat /usr/bin/bzip2recover "${BZIP2_DEST}/usr/bin/"
cp -a /usr/bin/bzdiff /usr/bin/bzgrep /usr/bin/bzmore "${BZIP2_DEST}/usr/bin/" 2>/dev/null || true
cp -a /usr/lib/libbz2.so* "${BZIP2_DEST}/usr/lib/" 2>/dev/null || cp -a /usr/lib64/libbz2.so* "${BZIP2_DEST}/usr/lib/"
cp -a /usr/include/bzlib.h "${BZIP2_DEST}/usr/include/"

cat << 'ENDTOML' > "${WORK_DIR}/recipe-bzip2.toml"
[package]
name = "bzip2"
version = "1.0.8"
release = 1
architecture = "x86_64"
summary = "Freely available, patent free, high-quality data compressor"
license = "BSD-like"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://sourceware.org/bzip2/"

[dependencies]
provides = [
    "bzip2 = 1.0.8",
    "lib:libbz2.so.1.0",
    "cmd:bzip2",
    "cmd:bunzip2",
    "cmd:bzcat"
]

[triggers]
run_ldconfig = true

[build]
script = """
cp -a "$CURRENT_DIR/build/aux_work/bzip2-dest/"* "$DESTDIR/"
"""
ENDTOML
"${BUILDER}" "${WORK_DIR}/recipe-bzip2.toml"

# 2. tar
TAR_DEST="${WORK_DIR}/tar-dest"
rm -rf "${TAR_DEST}"
mkdir -p "${TAR_DEST}/usr/bin"
cp -a /usr/bin/tar "${TAR_DEST}/usr/bin/"

cat << 'ENDTOML' > "${WORK_DIR}/recipe-tar.toml"
[package]
name = "tar"
version = "1.35"
release = 1
architecture = "x86_64"
summary = "GNU Tar archiver"
license = "GPL-3.0-or-later"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://www.gnu.org/software/tar/"

[dependencies]
provides = ["tar = 1.35", "cmd:tar"]

[build]
script = """
cp -a "$CURRENT_DIR/build/aux_work/tar-dest/"* "$DESTDIR/"
"""
ENDTOML
"${BUILDER}" "${WORK_DIR}/recipe-tar.toml"

# 3. gzip
GZIP_DEST="${WORK_DIR}/gzip-dest"
rm -rf "${GZIP_DEST}"
mkdir -p "${GZIP_DEST}/usr/bin"
cp -a /usr/bin/gzip /usr/bin/gunzip /usr/bin/zcat "${GZIP_DEST}/usr/bin/"

cat << 'ENDTOML' > "${WORK_DIR}/recipe-gzip.toml"
[package]
name = "gzip"
version = "1.15"
release = 1
architecture = "x86_64"
summary = "GNU compression utility"
license = "GPL-3.0-or-later"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://www.gnu.org/software/gzip/"

[dependencies]
provides = ["gzip = 1.15", "cmd:gzip", "cmd:gunzip", "cmd:zcat"]

[build]
script = """
cp -a "$CURRENT_DIR/build/aux_work/gzip-dest/"* "$DESTDIR/"
"""
ENDTOML
"${BUILDER}" "${WORK_DIR}/recipe-gzip.toml"

# 4. diffutils
DIFF_DEST="${WORK_DIR}/diffutils-dest"
rm -rf "${DIFF_DEST}"
mkdir -p "${DIFF_DEST}/usr/bin"
cp -a /usr/bin/diff /usr/bin/cmp /usr/bin/diff3 /usr/bin/sdiff "${DIFF_DEST}/usr/bin/"

cat << 'ENDTOML' > "${WORK_DIR}/recipe-diffutils.toml"
[package]
name = "diffutils"
version = "3.12"
release = 1
architecture = "x86_64"
summary = "GNU diff utilities"
license = "GPL-3.0-or-later"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://www.gnu.org/software/diffutils/"

[dependencies]
provides = ["diffutils = 3.12", "cmd:diff", "cmd:cmp"]

[build]
script = """
cp -a "$CURRENT_DIR/build/aux_work/diffutils-dest/"* "$DESTDIR/"
"""
ENDTOML
"${BUILDER}" "${WORK_DIR}/recipe-diffutils.toml"

# 5. patch
PATCH_DEST="${WORK_DIR}/patch-dest"
rm -rf "${PATCH_DEST}"
mkdir -p "${PATCH_DEST}/usr/bin"
cp -a /usr/bin/patch "${PATCH_DEST}/usr/bin/"

cat << 'ENDTOML' > "${WORK_DIR}/recipe-patch.toml"
[package]
name = "patch"
version = "2.8"
release = 1
architecture = "x86_64"
summary = "GNU patch utility"
license = "GPL-3.0-or-later"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://savannah.gnu.org/projects/patch/"

[dependencies]
provides = ["patch = 2.8", "cmd:patch"]

[build]
script = """
cp -a "$CURRENT_DIR/build/aux_work/patch-dest/"* "$DESTDIR/"
"""
ENDTOML
"${BUILDER}" "${WORK_DIR}/recipe-patch.toml"

# 6. findutils
FIND_DEST="${WORK_DIR}/findutils-dest"
rm -rf "${FIND_DEST}"
mkdir -p "${FIND_DEST}/usr/bin"
cp -a /usr/bin/find /usr/bin/xargs "${FIND_DEST}/usr/bin/"

cat << 'ENDTOML' > "${WORK_DIR}/recipe-findutils.toml"
[package]
name = "findutils"
version = "4.11.0"
release = 1
architecture = "x86_64"
summary = "GNU utilities for finding files"
license = "GPL-3.0-or-later"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://www.gnu.org/software/findutils/"

[dependencies]
provides = ["findutils = 4.11.0", "cmd:find", "cmd:xargs"]

[build]
script = """
cp -a "$CURRENT_DIR/build/aux_work/findutils-dest/"* "$DESTDIR/"
"""
ENDTOML
"${BUILDER}" "${WORK_DIR}/recipe-findutils.toml"

# 7. grep
GREP_DEST="${WORK_DIR}/grep-dest"
rm -rf "${GREP_DEST}"
mkdir -p "${GREP_DEST}/usr/bin"
cp -a /usr/bin/grep /usr/bin/egrep /usr/bin/fgrep "${GREP_DEST}/usr/bin/"

cat << 'ENDTOML' > "${WORK_DIR}/recipe-grep.toml"
[package]
name = "grep"
version = "3.12"
release = 1
architecture = "x86_64"
summary = "GNU grep pattern matching utility"
license = "GPL-3.0-or-later"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://www.gnu.org/software/grep/"

[dependencies]
provides = ["grep = 3.12", "cmd:grep", "cmd:egrep", "cmd:fgrep"]

[build]
script = """
cp -a "$CURRENT_DIR/build/aux_work/grep-dest/"* "$DESTDIR/"
"""
ENDTOML
"${BUILDER}" "${WORK_DIR}/recipe-grep.toml"

# 8. sed
SED_DEST="${WORK_DIR}/sed-dest"
rm -rf "${SED_DEST}"
mkdir -p "${SED_DEST}/usr/bin"
cp -a /usr/bin/sed "${SED_DEST}/usr/bin/"

cat << 'ENDTOML' > "${WORK_DIR}/recipe-sed.toml"
[package]
name = "sed"
version = "4.10"
release = 1
architecture = "x86_64"
summary = "GNU stream editor"
license = "GPL-3.0-or-later"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://www.gnu.org/software/sed/"

[dependencies]
provides = ["sed = 4.10", "cmd:sed"]

[build]
script = """
cp -a "$CURRENT_DIR/build/aux_work/sed-dest/"* "$DESTDIR/"
"""
ENDTOML
"${BUILDER}" "${WORK_DIR}/recipe-sed.toml"

# 9. gawk
GAWK_DEST="${WORK_DIR}/gawk-dest"
rm -rf "${GAWK_DEST}"
mkdir -p "${GAWK_DEST}/usr/bin" "${GAWK_DEST}/usr/lib/gawk" "${GAWK_DEST}/usr/share/awk"
cp -a /usr/bin/gawk "${GAWK_DEST}/usr/bin/"
cp -a /usr/lib/gawk/* "${GAWK_DEST}/usr/lib/gawk/" 2>/dev/null || true
cp -a /usr/share/awk/* "${GAWK_DEST}/usr/share/awk/" 2>/dev/null || true

cat << 'ENDTOML' > "${WORK_DIR}/recipe-gawk.toml"
[package]
name = "gawk"
version = "5.4.1"
release = 1
architecture = "x86_64"
summary = "GNU pattern scanning and processing language"
license = "GPL-3.0-or-later"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://www.gnu.org/software/gawk/"

[dependencies]
provides = ["gawk = 5.4.1", "cmd:gawk", "cmd:awk"]

[build]
script = """
cp -a "$CURRENT_DIR/build/aux_work/gawk-dest/"* "$DESTDIR/"
"""
ENDTOML
"${BUILDER}" "${WORK_DIR}/recipe-gawk.toml"

# 10. which
WHICH_DEST="${WORK_DIR}/which-dest"
rm -rf "${WHICH_DEST}"
mkdir -p "${WHICH_DEST}/usr/bin"
cp -a /usr/bin/which "${WHICH_DEST}/usr/bin/"

cat << 'ENDTOML' > "${WORK_DIR}/recipe-which.toml"
[package]
name = "which"
version = "2.21"
release = 1
architecture = "x86_64"
summary = "Displays where a particular program is in the user's search path"
license = "GPL-3.0-or-later"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://savannah.gnu.org/projects/which/"

[dependencies]
provides = ["which = 2.21", "cmd:which"]

[build]
script = """
cp -a "$CURRENT_DIR/build/aux_work/which-dest/"* "$DESTDIR/"
"""
ENDTOML
"${BUILDER}" "${WORK_DIR}/recipe-which.toml"

# 11. m4
M4_DEST="${WORK_DIR}/m4-dest"
rm -rf "${M4_DEST}"
mkdir -p "${M4_DEST}/usr/bin"
cp -a /usr/bin/m4 "${M4_DEST}/usr/bin/"

cat << 'ENDTOML' > "${WORK_DIR}/recipe-m4.toml"
[package]
name = "m4"
version = "1.4.21"
release = 1
architecture = "x86_64"
summary = "GNU macro processor"
license = "GPL-3.0-or-later"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://www.gnu.org/software/m4/"

[dependencies]
provides = ["m4 = 1.4.21", "cmd:m4"]

[build]
script = """
cp -a "$CURRENT_DIR/build/aux_work/m4-dest/"* "$DESTDIR/"
"""
ENDTOML
"${BUILDER}" "${WORK_DIR}/recipe-m4.toml"

# 12. blaze-builder
BUILDER_DEST="${WORK_DIR}/blaze-builder-dest"
rm -rf "${BUILDER_DEST}"
mkdir -p "${BUILDER_DEST}/usr/bin" "${BUILDER_DEST}/usr/share/blaze/recipes" "${BUILDER_DEST}/usr/share/blaze/sources"
if [ -f "${BLAZE_ROOT}/target/release/blaze-builder" ]; then
    cp -a "${BLAZE_ROOT}/target/release/blaze-builder" "${BUILDER_DEST}/usr/bin/"
else
    cp -a "${BLAZE_ROOT}/target/debug/blaze-builder" "${BUILDER_DEST}/usr/bin/"
fi
cp -a "${BLAZE_ROOT}/recipes/"* "${BUILDER_DEST}/usr/share/blaze/recipes/"
cp -a "${BLAZE_ROOT}/build/sources/zlib-1.3.1.tar.gz" "${BUILDER_DEST}/usr/share/blaze/sources/"

cat << 'ENDTOML' > "${WORK_DIR}/recipe-blaze-builder.toml"
[package]
name = "blaze-builder"
version = "0.1.0"
release = 1
architecture = "x86_64"
summary = "BlazeOS Native Package Builder Engine"
license = "MIT OR Apache-2.0"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://blazeos.org"

[dependencies]
provides = ["blaze-builder = 0.1.0", "cmd:blaze-builder"]

[build]
script = """
cp -a "$CURRENT_DIR/build/aux_work/blaze-builder-dest/"* "$DESTDIR/"
"""
ENDTOML
"${BUILDER}" "${WORK_DIR}/recipe-blaze-builder.toml"

echo "=== Stage 3.1 Auxiliary Packages Built Successfully ==="
ls -lh "${PKGS_DIR}/"*.blz
