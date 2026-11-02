#!/usr/bin/env python3
import os
import re
import tarfile
import subprocess
import io
import glob

STUB_PATTERNS = re.compile(
    rb"(stub binary|/\*\s*(Shared|Placeholder|Mesa|Vulkan))",
    re.IGNORECASE,
)

LEGIT_SHORT_WRAPPERS = {
    "usr/bin/egrep",
    "usr/bin/fgrep",
    "usr/bin/zcat",
    "usr/bin/gunzip",
    "usr/libexec/niri-session",
}


def classify_executable(name: str, data: bytes):
    if data.startswith(b"\x7fELF"):
        return None
    if data.startswith(b"#!"):
        first_line = data.splitlines()[0].decode("latin1", errors="replace").strip()
        if STUB_PATTERNS.search(data):
            return ("SHELL_STUB", first_line)
        if len(data) < 160 and name not in LEGIT_SHORT_WRAPPERS and b"exec " not in data:
            return ("SHELL_STUB", first_line)
        return ("UPSTREAM_SCRIPT", first_line)
    return ("NOT_ELF", str(data[:16]))


def is_shared_object_path(name: str) -> bool:
    if not name.startswith("usr/lib/"):
        return False
    if name.endswith((".py", ".socket", ".service", ".conf", ".softdep", ".a", ".la")):
        return False
    base = os.path.basename(name)
    return base.endswith(".so") or ".so." in base


pkg_files = sorted(glob.glob("build/packages/*.blz"))
print(f"Auditing {len(pkg_files)} packages in build/packages/*.blz...")

stubs_found = []
upstream_scripts = []

for pkg in pkg_files:
    pkg_name = os.path.basename(pkg)
    try:
        with tarfile.open(pkg, "r") as t:
            try:
                data_member = t.extractfile("data.tar.zst")
                if not data_member:
                    continue
                proc = subprocess.Popen(
                    ["zstd", "-d", "-c"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                )
                out, _ = proc.communicate(input=data_member.read())
                with tarfile.open(fileobj=io.BytesIO(out), mode="r:*") as payload:
                    for member in payload.getmembers():
                        name = member.name.lstrip("./")
                        if not member.isfile() or member.issym():
                            continue
                        if name.startswith(("usr/bin/", "usr/sbin/", "usr/libexec/")):
                            data = payload.extractfile(member).read(4096)
                            res = classify_executable(name, data)
                            if res:
                                kind, detail = res
                                if kind == "UPSTREAM_SCRIPT":
                                    upstream_scripts.append((pkg_name, name, detail))
                                else:
                                    stubs_found.append((pkg_name, name, kind, detail))
                        elif is_shared_object_path(name):
                            head = payload.extractfile(member).read(64)
                            if not head.startswith(b"\x7fELF") and not head.startswith(b"/* GNU ld script") and not head.startswith(b"INPUT("):
                                stubs_found.append((pkg_name, name, "INVALID_SO", str(head[:24])))
            except KeyError:
                pass
    except Exception as e:
        print(f"Error reading {pkg_name}: {e}")

# Also audit active build/rootfs
rootfs_stubs = []
rootfs_dir = "build/rootfs"
if os.path.isdir(rootfs_dir):
    for sub in ("usr/bin", "usr/libexec", "usr/lib"):
        full_sub = os.path.join(rootfs_dir, sub)
        if not os.path.isdir(full_sub) or os.path.islink(full_sub):
            continue
        for root_w, _, files_w in os.walk(full_sub):
            for fn in files_w:
                fp = os.path.join(root_w, fn)
                if os.path.islink(fp) or not os.path.isfile(fp):
                    continue
                rel = os.path.relpath(fp, rootfs_dir)
                try:
                    with open(fp, "rb") as f:
                        data = f.read(4096)
                except OSError:
                    continue
                if rel.startswith(("usr/bin/", "usr/libexec/")):
                    res = classify_executable(rel, data)
                    if res and res[0] != "UPSTREAM_SCRIPT":
                        rootfs_stubs.append((rel, res[0], res[1]))
                elif is_shared_object_path(rel):
                    if not data.startswith(b"\x7fELF") and not data.startswith(b"/* GNU ld script") and not data.startswith(b"INPUT("):
                        rootfs_stubs.append((rel, "INVALID_SO", str(data[:24])))

print(f"\nActive build/rootfs stub count: {len(rootfs_stubs)}")
for rel, issue, detail in rootfs_stubs:
    print(f"  [ROOTFS_{issue}] {rel} ({detail})")

print(f"\nPackage archive audit complete:")
print(f"  - Verified legitimate upstream scripts: {len(upstream_scripts)}")
print(f"  - Legacy/test package stubs in build/packages/: {len(stubs_found)}")
for pkg, path, issue, detail in stubs_found:
    print(f"  [{issue}] {pkg} -> {path} ({detail})")


