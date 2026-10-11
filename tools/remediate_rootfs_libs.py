#!/usr/bin/env python3
"""
Rootfs runtime-library audit/remediation (package-aware, unmanaged stub replacement).

Policy (M9 Phase B.1.1):
  * NEVER modify, delete, truncate or re-link any path owned by a Portadora
    package (recorded in package_files of /var/lib/portadora/db.sqlite).
  * Package-managed files are installed and verified exclusively through Portadora.
  * For UNOWNED shared library dependencies: ensure that the destination file
    and SONAME symlink are valid 64-bit ELF binaries, replacing any placeholder
    text stubs (e.g. from early bootstrap dest trees) with real ELF shared objects.
"""
import os
import shutil
import sqlite3
import subprocess
import sys

BLAZE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ROOTFS_DIR = os.path.join(BLAZE_ROOT, "build", "rootfs")
if len(sys.argv) > 1 and not sys.argv[1].startswith("--"):
    ROOTFS_DIR = os.path.abspath(sys.argv[1])
ROOTFS_LIB = os.path.join(ROOTFS_DIR, "usr", "lib")
DRY_RUN = "--dry-run" in sys.argv

print(f"=== Rootfs Shared Library Remediation on {ROOTFS_DIR} ===")

# 0. Load the set of package-owned paths
owned = set()
db_path = os.path.join(ROOTFS_DIR, "var", "lib", "portadora", "db.sqlite")
if os.path.exists(db_path):
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    owned = {r[0] for r in con.execute("SELECT path FROM package_files")}
    con.close()
print(f"[AUDIT] {len(owned)} package-owned paths loaded (protected)")


def rel(path):
    return os.path.relpath(path, ROOTFS_DIR)


def is_valid_elf(path):
    """Check if file exists and starts with ELF magic bytes."""
    if not os.path.exists(path):
        return False
    try:
        with open(path, "rb") as f:
            return f.read(4) == b"\x7fELF"
    except Exception:
        return False


# 1. Fix /run/user/1000 ownership (runtime directory, not package content)
if not DRY_RUN:
    os.makedirs(os.path.join(ROOTFS_DIR, "run", "user", "1000"), exist_ok=True)
    subprocess.run(f"chown -R 1000:1000 '{ROOTFS_DIR}/run/user/1000'", shell=True, check=False)
    subprocess.run(f"chmod 0700 '{ROOTFS_DIR}/run/user/1000'", shell=True, check=False)

# 2. Collect all executable binaries in rootfs
binaries = []
for root, dirs, files in os.walk(ROOTFS_DIR):
    if rel(root).startswith(("usr/lib/modules", "usr/lib/firmware", "proc", "sys", "dev")):
        dirs[:] = []
        continue
    for f in files:
        fp = os.path.join(root, f)
        if os.access(fp, os.X_OK) and not os.path.islink(fp):
            binaries.append(fp)

# 3. Resolve all shared library dependencies via ldd
req_libs = {}
for b in binaries:
    try:
        out = subprocess.check_output(["ldd", b], text=True, stderr=subprocess.DEVNULL)
    except Exception:
        continue
    for line in out.splitlines():
        line = line.strip()
        if "=>" in line:
            parts = line.split("=>")
            lib_name = os.path.basename(parts[0].strip())
            tokens = parts[1].strip().split()
            if tokens and os.path.exists(tokens[0]):
                req_libs[lib_name] = tokens[0]

added, replaced_stubs, skipped_owned = [], [], []
for lib_name, host_path in sorted(req_libs.items()):
    real_host_file = os.path.realpath(host_path)
    real_basename = os.path.basename(real_host_file)
    dest_real = os.path.join(ROOTFS_LIB, real_basename)
    dest_link = os.path.join(ROOTFS_LIB, lib_name)

    targets = [dest_real] + ([dest_link] if lib_name != real_basename else [])
    # CRITICAL: Under no circumstances modify any file owned by a Portadora package
    if any(rel(t) in owned for t in targets):
        skipped_owned.append(lib_name)
        continue

    # Ensure dest_real is a real ELF binary
    if not is_valid_elf(dest_real):
        if os.path.lexists(dest_real):
            replaced_stubs.append(rel(dest_real))
            if not DRY_RUN:
                os.remove(dest_real)
        else:
            added.append(rel(dest_real))
        if not DRY_RUN:
            shutil.copy2(real_host_file, dest_real)

    # Ensure dest_link is a valid symlink pointing to real_basename
    if lib_name != real_basename:
        need_relink = False
        if not os.path.islink(dest_link):
            need_relink = True
        else:
            try:
                if os.readlink(dest_link) != real_basename or not is_valid_elf(dest_link):
                    need_relink = True
            except Exception:
                need_relink = True

        if need_relink:
            if os.path.lexists(dest_link):
                if not DRY_RUN:
                    os.remove(dest_link)
            if not DRY_RUN:
                os.symlink(real_basename, dest_link)
            added.append(rel(dest_link))

print(f"[AUDIT] {len(skipped_owned)} libs provided by packages (untouched)")
print(f"[AUDIT] {len(replaced_stubs)} unowned text stubs replaced with real host ELF")
print(f"[AUDIT] {len(added)} unowned libraries/symlinks ensured")
print("=== Remediation Complete ===")
