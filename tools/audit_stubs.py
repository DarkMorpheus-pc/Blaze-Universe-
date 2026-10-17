#!/usr/bin/env python3
import os
import tarfile
import subprocess
import io
import glob

pkg_files = sorted(glob.glob("build/packages/*.blz"))
print(f"Auditing {len(pkg_files)} packages for binary stubs...")

stubs_found = []

for pkg in pkg_files:
    pkg_name = os.path.basename(pkg)
    try:
        with tarfile.open(pkg, "r") as t:
            try:
                data_member = t.extractfile("data.tar.zst")
                if not data_member:
                    continue
                # Use system zstd to decompress
                proc = subprocess.Popen(["zstd", "-d", "-c"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                out, _ = proc.communicate(input=data_member.read())
                with tarfile.open(fileobj=io.BytesIO(out), mode="r:*") as payload:
                    for member in payload.getmembers():
                        name = member.name.lstrip("./")
                        # Check executables
                        if name.startswith("usr/bin/") or name.startswith("usr/sbin/") or name.startswith("usr/libexec/"):
                            if member.isfile():
                                f = payload.extractfile(member)
                                head = f.read(16)
                                if head.startswith(b"#!"):
                                    stubs_found.append((pkg_name, name, "SHELL_STUB", head[:16].decode("latin1", errors="replace").strip()))
                                elif not head.startswith(b"\x7fELF"):
                                    stubs_found.append((pkg_name, name, "NOT_ELF", str(head[:8])))
                        # Check shared libraries
                        elif name.startswith("usr/lib/") and (".so" in name) and not member.issym():
                            if member.isfile():
                                f = payload.extractfile(member)
                                head = f.read(16)
                                if not head.startswith(b"\x7fELF") and not head.startswith(b"/* GNU ld script"):
                                    stubs_found.append((pkg_name, name, "INVALID_SO", str(head[:8])))
            except KeyError:
                pass
    except Exception as e:
        print(f"Error reading {pkg_name}: {e}")

print(f"\nAudit complete. Found {len(stubs_found)} stubs/fakes in binary paths:")
for pkg, path, issue, detail in stubs_found:
    print(f"  [{issue}] {pkg} -> {path} ({detail})")

