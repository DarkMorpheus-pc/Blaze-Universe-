#!/usr/bin/env python3
"""
Rootfs runtime-library audit/remediation (package-aware, unmanaged stub replacement).

Policy (M9 Phase B.1.1):
  * NEVER modify, delete, truncate or re-link any path owned by a Portadora
    package (recorded in package_files of /var/lib/portadora/db.sqlite).
  * Package-managed files are installed and verified exclusively through Portadora.
  * For UNOWNED shared library dependencies and stubs in /usr/lib:
    ensure that every shared library is a valid 64-bit ELF binary. Any placeholder
    text stub (header != b'\x7fELF') is replaced with the corresponding real ELF
    from the host system (/usr/lib).
  * Ensures essential system data directories (/usr/share/X11/xkb,
    /usr/share/xkeyboard-config-2, /usr/share/libinput) exist for runtime graphics.
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
HOST_LIB = "/usr/lib"
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

# 2. Ensure real seatd binary
if not DRY_RUN and os.path.exists("/usr/bin/seatd"):
    seatd_dest = os.path.join(ROOTFS_DIR, "usr", "bin", "seatd")
    if not is_valid_elf(seatd_dest) and rel(seatd_dest) not in owned:
        shutil.copy2("/usr/bin/seatd", seatd_dest)
        os.chmod(seatd_dest, 0o755)

# 3. Ensure xkb keyboard data and libinput quirks exist
if not DRY_RUN:
    # X11/xkb
    xkb_dest = os.path.join(ROOTFS_DIR, "usr", "share", "X11", "xkb")
    if not os.path.exists(xkb_dest) and os.path.exists("/usr/share/X11/xkb"):
        os.makedirs(os.path.dirname(xkb_dest), exist_ok=True)
        shutil.copytree("/usr/share/X11/xkb", xkb_dest, dirs_exist_ok=True)

    # xkeyboard-config-2
    xkb2_dest = os.path.join(ROOTFS_DIR, "usr", "share", "xkeyboard-config-2")
    if not os.path.exists(xkb2_dest) and os.path.exists("/usr/share/X11/xkb"):
        os.makedirs(os.path.dirname(xkb2_dest), exist_ok=True)
        shutil.copytree("/usr/share/X11/xkb", xkb2_dest, dirs_exist_ok=True)

    # libinput quirks
    quirks_dest = os.path.join(ROOTFS_DIR, "usr", "share", "libinput")
    if not os.path.exists(quirks_dest) and os.path.exists("/usr/share/libinput"):
        os.makedirs(os.path.dirname(quirks_dest), exist_ok=True)
    # glvnd egl_vendor.d
    glvnd_dest = os.path.join(ROOTFS_DIR, "usr", "share", "glvnd")
    if not os.path.exists(glvnd_dest) and os.path.exists("/usr/share/glvnd"):
        os.makedirs(os.path.dirname(glvnd_dest), exist_ok=True)
        shutil.copytree("/usr/share/glvnd", glvnd_dest, dirs_exist_ok=True)

    # fontconfig definitions
    fc_dest = os.path.join(ROOTFS_DIR, "usr", "share", "fontconfig")
    if not os.path.exists(fc_dest) and os.path.exists("/usr/share/fontconfig"):
        os.makedirs(os.path.dirname(fc_dest), exist_ok=True)
        shutil.copytree("/usr/share/fontconfig", fc_dest, dirs_exist_ok=True)

# 4. Sweep all .so files in ROOTFS_LIB and subdirs (like dri/)
replaced_stubs = []
for root, dirs, files in os.walk(ROOTFS_LIB):
    if rel(root).startswith(("usr/lib/modules", "usr/lib/firmware")):
        dirs[:] = []
        continue
    for f in files:
        if ".so" not in f:
            continue
        fp = os.path.join(root, f)
        if os.path.islink(fp):
            continue
        rpath = rel(fp)
        if rpath in owned:
            continue
        if not is_valid_elf(fp):
            # Find candidate on host
            candidate = None
            sub_rel = os.path.relpath(fp, ROOTFS_LIB)
            exact_host = os.path.join(HOST_LIB, sub_rel)
            if is_valid_elf(exact_host):
                candidate = exact_host
            else:
                prefix = f.split(".so")[0] + ".so"
                for hf in os.listdir(HOST_LIB):
                    if hf.startswith(prefix) and not os.path.islink(os.path.join(HOST_LIB, hf)):
                        cand = os.path.join(HOST_LIB, hf)
                        if is_valid_elf(cand):
                            candidate = cand
                            break
            if candidate:
                replaced_stubs.append((rpath, candidate))
                if not DRY_RUN:
                    os.remove(fp)
                    shutil.copy2(candidate, fp)

# 5. Collect all executable binaries in rootfs and resolve missing direct dependencies
binaries = []
for root, dirs, files in os.walk(ROOTFS_DIR):
    if rel(root).startswith(("usr/lib/modules", "usr/lib/firmware", "proc", "sys", "dev")):
        dirs[:] = []
        continue
    for f in files:
        fp = os.path.join(root, f)
        if os.access(fp, os.X_OK) and not os.path.islink(fp):
            binaries.append(fp)

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

added = []
for lib_name, host_path in sorted(req_libs.items()):
    real_host_file = os.path.realpath(host_path)
    real_basename = os.path.basename(real_host_file)
    dest_real = os.path.join(ROOTFS_LIB, real_basename)
    dest_link = os.path.join(ROOTFS_LIB, lib_name)

    targets = [dest_real] + ([dest_link] if lib_name != real_basename else [])
    if any(rel(t) in owned for t in targets):
        continue

    if not is_valid_elf(dest_real):
        if not DRY_RUN:
            if os.path.lexists(dest_real):
                os.remove(dest_real)
            shutil.copy2(real_host_file, dest_real)
        added.append(rel(dest_real))

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
            if not DRY_RUN:
                if os.path.lexists(dest_link):
                    os.remove(dest_link)
                os.symlink(real_basename, dest_link)
            added.append(rel(dest_link))

print(f"[AUDIT] {len(replaced_stubs)} unowned text stubs replaced with real host ELF")
print(f"[AUDIT] {len(added)} unowned libraries/symlinks ensured")
print("=== Remediation Complete ===")
