#!/usr/bin/env python3
# ==============================================================================
# Blaze Universe — systemd unit-set synchronisation (INTERIM)
#
# The rootfs currently carries systemd binaries whose provenance is the host
# systemd package (libsystemd-shared-<ver>.so), but only a hand-picked subset of
# its unit files. Without the full unit set essential services never run
# (systemd-sysctl, random-seed, journal-flush, timesyncd, user@.service ...).
#
# This tool copies the unit files, .wants wiring, tmpfiles.d, sysusers.d and
# presets that belong to the *same* systemd version from the host package
# database, refusing to run on a version mismatch. It is a stop-gap until
# systemd is built from source by blaze-builder (Honesty Gate, Phase 2).
# ==============================================================================
import glob
import os
import re
import shutil
import subprocess
import sys

BLAZE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ROOTFS = os.path.abspath(os.environ.get("BLAZE_ROOTFS", os.path.join(BLAZE_ROOT, "build", "rootfs")))

PREFIXES = (
    "usr/lib/systemd/system/",
    "usr/lib/systemd/user/",
    "usr/lib/systemd/system-preset/",
    "usr/lib/systemd/user-preset/",
    "usr/lib/systemd/system-generators/",
    "usr/lib/systemd/user-generators/",
    "usr/lib/tmpfiles.d/",
    "usr/lib/sysusers.d/",
    "usr/lib/sysctl.d/",
    "usr/lib/udev/rules.d/",
)
# Units that only make sense on systems with features Blaze does not ship yet.
SKIP = re.compile(r"(homed|portabled|machined|importd|journal-remote|journal-upload|"
                  r"cryptsetup|veritysetup|integritysetup|nspawn|mountfsd|nsresourced|"
                  r"storagetm|sysupdate|pcr|tpm2|repart|bsod|ssh-generator|ssh-proxy|"
                  r"soft-reboot|confext|sysext|vmspawn|oomd|boot-update|bootctl|"
                  r"factory-reset|keyutil|creds)")


def rootfs_systemd_version():
    libs = glob.glob(os.path.join(ROOTFS, "usr/lib/systemd/libsystemd-shared-*.so"))
    if not libs:
        sys.exit("[ERROR] no libsystemd-shared in rootfs")
    return re.search(r"libsystemd-shared-(.+)\.so$", libs[0]).group(1)


def host_package_files():
    q = subprocess.run(["pacman", "-Q", "systemd"], capture_output=True, text=True)
    if q.returncode != 0:
        sys.exit("[ERROR] host has no pacman systemd package; cannot sync units")
    ver = q.stdout.split()[1]
    files = subprocess.run(["pacman", "-Qlq", "systemd"], capture_output=True, text=True,
                           check=True).stdout.split("\n")
    return ver, [f.lstrip("/") for f in files if f and not f.endswith("/")]


def exec_binaries(unit_path):
    bins = []
    try:
        with open(unit_path, errors="replace") as f:
            for line in f:
                m = re.match(r"\s*ExecStart=[-@:+!]*(\S+)", line)
                if m:
                    bins.append(m.group(1))
    except OSError:
        pass
    return bins


def binary_exists_in_rootfs(cmd):
    if cmd.startswith("/"):
        rel = cmd.lstrip("/")
        if os.path.exists(os.path.join(ROOTFS, rel)):
            return True
        # UsrMerge fallback (/bin/foo -> usr/bin/foo, /sbin/foo -> usr/bin/foo)
        for prefix in ("bin/", "sbin/", "usr/sbin/"):
            if rel.startswith(prefix):
                alt = "usr/bin/" + rel[len(prefix):]
                if os.path.exists(os.path.join(ROOTFS, alt)):
                    return True
        return False
    # Bare command name (systemd searches /usr/bin, /usr/sbin, /usr/lib/systemd)
    for search_dir in ("usr/bin", "usr/sbin", "usr/lib/systemd"):
        if os.path.exists(os.path.join(ROOTFS, search_dir, cmd)):
            return True
    return False


def main():
    rver = rootfs_systemd_version()
    hver, files = host_package_files()
    if rver != hver:
        sys.exit(f"[ERROR] version mismatch: rootfs systemd {rver} vs host package {hver}. "
                 "Refusing to mix unit files from a different release.")
    copied = skipped = kept = 0
    for rel in files:
        if not rel.startswith(PREFIXES):
            continue
        name = os.path.basename(rel)
        if SKIP.search(name):
            skipped += 1
            continue
        src = "/" + rel
        dst = os.path.join(ROOTFS, rel)
        if not os.path.lexists(src):
            continue
        # A unit is only useful if every binary it executes exists in the rootfs.
        if rel.endswith(".service") and not os.path.islink(src):
            missing = [b for b in exec_binaries(src) if not binary_exists_in_rootfs(b)]
            if missing:
                if os.path.lexists(dst):
                    os.unlink(dst)
                skipped += 1
                continue
        if os.path.lexists(dst) and not os.path.islink(src):
            kept += 1          # never overwrite a file Blaze already provides
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.islink(src):
            if os.path.lexists(dst):
                os.unlink(dst)
            os.symlink(os.readlink(src), dst)
        else:
            shutil.copy2(src, dst)
        copied += 1
    # Drop dangling symlinks (aliases / .wants pointing at skipped units).
    dangling = 0
    for base in ("usr/lib/systemd/system", "usr/lib/systemd/user"):
        for dirpath, _, names in os.walk(os.path.join(ROOTFS, base)):
            for l in names:
                p = os.path.join(dirpath, l)
                if not os.path.islink(p):
                    continue
                target = os.readlink(p)
                unit_dir = os.path.join(ROOTFS, base)
                cand = os.path.join(unit_dir, os.path.basename(target))
                # template instances (foo@bar.service -> foo@.service) resolve to the template
                if not os.path.exists(cand):
                    os.unlink(p)
                    dangling += 1
    # Interactive first-boot prompts would block an unattended boot; the
    # Solar Installer performs locale/keymap/timezone/user setup instead.
    # Also remove duplicate getty@ttyS0 and console-getty wants links so they
    # do not collide with systemd-getty-generator's serial-getty@ttyS0.service.
    for blocker in (
        "sysinit.target.wants/systemd-firstboot.service",
        "getty.target.wants/getty@ttyS0.service",
        "getty.target.wants/console-getty.service",
    ):
        p = os.path.join(ROOTFS, "usr/lib/systemd/system", blocker)
        if os.path.lexists(p):
            os.unlink(p)
    print(f"[UNITS] systemd {rver}: copied {copied}, kept existing {kept}, skipped {skipped}, "
          f"removed {dangling} dangling wants-links")


if __name__ == "__main__":
    main()
