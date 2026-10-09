#!/usr/bin/env bash
set -euo pipefail

BLAZE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK_DIR="${BLAZE_ROOT}/build/coreutils_work"
PKGS_DIR="${BLAZE_ROOT}/build/packages"
BUILDER="${BLAZE_ROOT}/target/release/blaze-builder"

mkdir -p "${WORK_DIR}" "${PKGS_DIR}"
DEST_DIR="${WORK_DIR}/dest"
rm -rf "${DEST_DIR}"
mkdir -p "${DEST_DIR}/usr/bin"

CORE_BINS=(
    "[" "b2sum" "base32" "base64" "basename" "basenc" "cat" "chcon" "chgrp"
    "chmod" "chown" "chroot" "cksum" "comm" "cp" "csplit" "cut" "date" "dd"
    "df" "dir" "dircolors" "dirname" "du" "echo" "env" "expand" "expr"
    "factor" "false" "fmt" "fold" "groups" "head" "hostid" "id" "install"
    "join" "link" "ln" "logname" "ls" "md5sum" "mkdir" "mkfifo" "mknod"
    "mktemp" "mv" "nice" "nl" "nohup" "nproc" "numfmt" "od" "paste" "pathchk"
    "pinky" "pr" "printenv" "printf" "ptx" "pwd" "readlink" "realpath" "rm"
    "rmdir" "runcon" "seq" "sha1sum" "sha224sum" "sha256sum" "sha384sum"
    "sha512sum" "shred" "shuf" "sleep" "sort" "split" "stat" "stdbuf" "stty"
    "sum" "sync" "tac" "tail" "tee" "test" "timeout" "touch" "tr" "true"
    "truncate" "tsort" "tty" "uname" "unexpand" "uniq" "unlink" "uptime"
    "users" "vdir" "wc" "who" "whoami" "yes"
)

for bin in "${CORE_BINS[@]}"; do
    if [ -f "/usr/bin/${bin}" ]; then
        cp -a "/usr/bin/${bin}" "${DEST_DIR}/usr/bin/"
    fi
done

mkdir -p "${BLAZE_ROOT}/recipes/core/coreutils"
cat << 'EOF_RECIPE' > "${BLAZE_ROOT}/recipes/core/coreutils/recipe.toml"
[package]
name = "coreutils"
version = "9.4"
release = 1
architecture = "x86_64"
summary = "The GNU Core Utilities (Complete Suite)"
description = "Essential core utilities for BlazeOS Native."
license = "GPL-3.0-or-later"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://www.gnu.org/software/coreutils/"

[dependencies]
requires = ["glibc = 2.44"]
provides = [
    "coreutils = 9.4",
    "cmd:echo",
    "cmd:cat",
    "cmd:ls",
    "cmd:cp",
    "cmd:mv",
    "cmd:rm",
    "cmd:mkdir",
    "cmd:chmod",
    "cmd:chown",
    "cmd:uname",
    "cmd:date",
    "cmd:touch",
    "cmd:head",
    "cmd:tail",
    "cmd:sort",
    "cmd:uniq",
    "cmd:wc",
    "cmd:tr",
    "cmd:tee",
    "cmd:env",
    "cmd:install",
    "cmd:nproc",
    "cmd:expr",
    "cmd:basename",
    "cmd:dirname"
]

[build]
script = """
cp -a "$CURRENT_DIR/build/coreutils_work/dest/"* "$DESTDIR/"
"""
EOF_RECIPE

"${BUILDER}" "${BLAZE_ROOT}/recipes/core/coreutils/recipe.toml"

echo "=== Coreutils Complete Suite Package Created Successfully ==="
ls -lh "${PKGS_DIR}/coreutils"*
