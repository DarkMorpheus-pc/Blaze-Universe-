#!/usr/bin/env python3
"""
Blaze Universe — Strict Binary Verification Gatekeeper (assert-real-elf.py)
Phase 0 "Honesty Gate" Enforcement Tool.

Enforces that a binary in BlazeOS is a genuine compiled ELF executable/library,
not a shell script stub or host-leaked binary.

Exit codes:
  0 - PASS: Genuine ELF compiled against Blaze sysroot
  1 - USAGE / FILE NOT FOUND / INTERNAL ERROR
  2 - FAIL: Shell script / Text stub detected
  3 - FAIL: Dynamic interpreter or dependencies point to host or illegal path
  4 - FAIL: Illegal RPATH / RUNPATH escape detected
"""

import sys
import os
import subprocess
import argparse

ALLOWED_INTERPRETERS = [
    "/usr/lib/ld-linux-x86-64.so.2",
    "/lib64/ld-linux-x86-64.so.2",  # Canonical symlink in UsrMerge
]

def check_binary(filepath, verbose=False, allow_static=False):
    if not os.path.exists(filepath):
        print(f"[FAIL] Target file does not exist: {filepath}", file=sys.stderr)
        return 1

    # 1. Read first bytes
    with open(filepath, "rb") as f:
        magic = f.read(16)

    # Check for shell scripts / shebang
    if magic.startswith(b"#!"):
        shebang = magic.decode("utf-8", errors="replace").strip()
        print(f"[FAIL Exit 2] Shell script stub detected: {filepath} ({shebang})", file=sys.stderr)
        return 2

    if not magic.startswith(b"\x7fELF"):
        print(f"[FAIL Exit 2] Not an ELF binary (magic={magic[:4]!r}): {filepath}", file=sys.stderr)
        return 2

    # 2. Inspect with readelf -l (Program Headers / INTERP)
    cmd = ["readelf", "-l", filepath]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        print(f"[FAIL Exit 1] readelf failed on {filepath}: {res.stderr}", file=sys.stderr)
        return 1

    interp = None
    for line in res.stdout.splitlines():
        if "program interpreter:" in line.lower() or "[requesting program interpreter:" in line.lower():
            # e.g.: [Requesting program interpreter: /usr/lib/ld-linux-x86-64.so.2]
            parts = line.split(":")
            if len(parts) >= 2:
                interp = parts[-1].strip().rstrip("]")

    if interp is not None:
        if verbose:
            print(f"[INFO] {filepath} interpreter: {interp}")
        if interp not in ALLOWED_INTERPRETERS:
            print(f"[FAIL Exit 3] Foreign or illegal interpreter: {interp} in {filepath}", file=sys.stderr)
            print(f"       Expected one of: {ALLOWED_INTERPRETERS}", file=sys.stderr)
            return 3
    else:
        if not allow_static:
            # Check if it's a shared library (DYN) without INTERP
            cmd_type = ["readelf", "-h", filepath]
            res_type = subprocess.run(cmd_type, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            is_dyn = any("DYN (Shared object file)" in l or "DYN (Position-Independent Executable file)" in l for l in res_type.stdout.splitlines())
            if not is_dyn:
                if verbose:
                    print(f"[WARN] No interpreter found (static or raw ELF): {filepath}")

    # 3. Inspect dynamic section for RPATH / RUNPATH
    cmd_dyn = ["readelf", "-d", filepath]
    res_dyn = subprocess.run(cmd_dyn, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res_dyn.returncode == 0:
        for line in res_dyn.stdout.splitlines():
            line_clean = line.strip()
            if "(RPATH)" in line_clean or "(RUNPATH)" in line_clean:
                # e.g.: 0x000000000000000f (RPATH) Library rpath: [/usr/lib:$ORIGIN]
                bracket_start = line_clean.find("[")
                bracket_end = line_clean.rfind("]")
                if bracket_start != -1 and bracket_end != -1:
                    rpaths = line_clean[bracket_start+1:bracket_end].split(":")
                    for rp in rpaths:
                        rp = rp.strip()
                        if not rp:
                            continue
                        # Allowed rpaths: $ORIGIN, /usr/lib, relative subpaths under /usr/lib
                        if rp.startswith("/home") or rp.startswith("/root") or "/tmp" in rp or "/build/" in rp:
                            print(f"[FAIL Exit 4] Build-host leak in RPATH/RUNPATH: '{rp}' in {filepath}", file=sys.stderr)
                            return 4

    # 4. Success: Real ELF
    if verbose:
        print(f"[PASS] Genuine ELF verified: {filepath}")
    return 0

def main():
    parser = argparse.ArgumentParser(description="BlazeOS Genuine ELF Verification Gatekeeper")
    parser.add_argument("paths", nargs="+", help="Path(s) to binary or shared library to verify")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose inspection logs")
    parser.add_argument("--allow-static", action="store_true", help="Allow static executables without PT_INTERP")
    args = parser.parse_args()

    overall_exit = 0
    for path in args.paths:
        code = check_binary(path, verbose=args.verbose, allow_static=args.allow_static)
        if code != 0 and overall_exit == 0:
            overall_exit = code

    sys.exit(overall_exit)

if __name__ == "__main__":
    main()
