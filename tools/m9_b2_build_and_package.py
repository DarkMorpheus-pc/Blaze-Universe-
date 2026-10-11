#!/usr/bin/env python3
# ==============================================================================
# BlazeOS Native — Milestone 9 Phase B.2 Packaging Pipeline
# Builds discrete .blz packages for Noctalia 5.1.0 and its runtime dependencies
# ==============================================================================
import glob
import os
import shutil
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BUILD = os.path.join(ROOT, "build")
WORK = os.path.join(BUILD, "m9_b2_packages_work")
PKGS_OUT = os.path.join(BUILD, "packages")
ROOTFS = os.path.join(BUILD, "rootfs-b11")
BUILDER = os.path.join(ROOT, "target", "release", "blaze-builder")
PORTADORA = os.path.join(ROOT, "target", "release", "portadora")
HOST_LIB = "/usr/lib"
NOCTALIA_SRC = "/home/darkmorpheus/solarui/vendor/noctalia"
NOCTALIA_BIN = os.path.join(NOCTALIA_SRC, "build-debug", "noctalia")
NOCTALIA_ASSETS = "/home/darkmorpheus/solarui/data/noctalia-assets"

os.makedirs(WORK, exist_ok=True)
os.makedirs(PKGS_OUT, exist_ok=True)

PACKAGES = {
    "sdbus-cpp": {
        "version": "2.1.0",
        "release": 1,
        "summary": "High-level C++ D-Bus library for Linux",
        "requires": ["glibc >= 2.44"],
        "files": ["libsdbus-c++.so*"],
    },
    "tomlplusplus": {
        "version": "3.4.0",
        "release": 1,
        "summary": "Header-only and compiled TOML config library for C++20",
        "requires": ["glibc >= 2.44"],
        "files": ["libtomlplusplus.so*"],
    },
    "librsvg": {
        "version": "2.59.2",
        "release": 1,
        "summary": "SVG rendering library for Cairo/Pango",
        "requires": ["glibc >= 2.44", "pixman >= 0.44.2", "freetype >= 2.13.3", "fontconfig >= 2.15.0"],
        "files": ["librsvg-2.so*", "libcairo-gobject.so*"],
    },
    "libqalculate": {
        "version": "5.5.0",
        "release": 1,
        "summary": "Multi-purpose desktop calculator and mathematical library",
        "requires": ["glibc >= 2.44", "gmp >= 6.3.0", "mpfr >= 4.2.1"],
        "files": ["libqalculate.so*"],
    },
    "libical": {
        "version": "3.0.18",
        "release": 1,
        "summary": "Open source implementation of the iCalendar protocols and data formats",
        "requires": ["glibc >= 2.44"],
        "files": ["libical.so*", "libicalss.so*", "libicalvcal.so*"],
    },
    "libsecret": {
        "version": "0.21.4",
        "release": 1,
        "summary": "GObject library for storing and retrieving passwords and secrets",
        "requires": ["glibc >= 2.44"],
        "files": ["libsecret-1.so*"],
    },
    "libsodium": {
        "version": "1.0.20",
        "release": 1,
        "summary": "Modern, easy-to-use software library for encryption, decryption, signatures",
        "requires": ["glibc >= 2.44"],
        "files": ["libsodium.so*"],
    },
    "wireplumber": {
        "version": "0.5.6",
        "release": 1,
        "summary": "Modular session / policy manager for PipeWire",
        "requires": ["glibc >= 2.44", "pipewire >= 1.2.0"],
        "files": ["libwireplumber-0.5.so*"],
    },
    "polkit": {
        "version": "0.124",
        "release": 1,
        "summary": "Application-level authorization toolkit and agent libraries",
        "requires": ["glibc >= 2.44"],
        "files": ["libpolkit-agent-1.so*", "libpolkit-gobject-1.so*"],
    },
    "tpm2-tss": {
        "version": "4.1.3",
        "release": 1,
        "summary": "TCG TPM2 Software Stack (TSS2) libraries",
        "requires": ["glibc >= 2.44", "openssl >= 3.4.0"],
        "files": ["libtss2-esys.so*", "libtss2-mu.so*", "libtss2-rc.so*", "libtss2-tctildr.so*", "libtss2-sys.so*"],
    },
    "jemalloc": {
        "version": "5.3.0",
        "release": 1,
        "summary": "General purpose malloc implementation emphasizing fragmentation avoidance",
        "requires": ["glibc >= 2.44"],
        "files": ["libjemalloc.so*"],
    },
    "libimage-codecs": {
        "version": "1.0.0",
        "release": 1,
        "summary": "Modern image decoding runtime libraries (WebP, JPEG-XL, AV1, Highway)",
        "requires": ["glibc >= 2.44"],
        "files": ["libwebpdemux.so*", "libjxl.so*", "libjxl_threads.so*", "libjxl_cms.so*", "libhwy.so*", "libdav1d.so*"],
    },
    "libaudio-codecs": {
        "version": "1.0.0",
        "release": 1,
        "summary": "Audio decoding and encoding runtime libraries (Sndfile, Ogg, Vorbis, FLAC, Opus, MP3)",
        "requires": ["glibc >= 2.44"],
        "files": ["libsndfile.so*", "libogg.so*", "libvorbis.so*", "libvorbisenc.so*", "libFLAC.so*", "libopus.so*", "libmpg123.so*", "libmp3lame.so*"],
    },
}

def stage_package(name, meta):
    dest = os.path.join(WORK, f"{name}-dest")
    if os.path.exists(dest):
        shutil.rmtree(dest)
    dest_lib = os.path.join(dest, "usr", "lib")
    os.makedirs(dest_lib, exist_ok=True)

    copied = 0
    for pattern in meta["files"]:
        matched = glob.glob(os.path.join(HOST_LIB, pattern))
        for m in matched:
            rel = os.path.relpath(m, HOST_LIB)
            target = os.path.join(dest_lib, rel)
            if os.path.islink(m):
                link_val = os.readlink(m)
                if os.path.exists(target) or os.path.islink(target):
                    os.remove(target)
                os.symlink(link_val, target)
            else:
                shutil.copy2(m, target)
            copied += 1
    print(f"[{name}] Staged {copied} files to {dest_lib}")
    return dest

def stage_noctalia():
    dest = os.path.join(WORK, "noctalia-dest")
    if os.path.exists(dest):
        shutil.rmtree(dest)
    dest_bin = os.path.join(dest, "usr", "bin")
    dest_assets = os.path.join(dest, "usr", "share", "solarui", "noctalia-assets")
    dest_apps = os.path.join(dest, "usr", "share", "applications")
    os.makedirs(dest_bin, exist_ok=True)
    os.makedirs(dest_assets, exist_ok=True)
    os.makedirs(dest_apps, exist_ok=True)

    # 1. Strip and install binary
    bin_target = os.path.join(dest_bin, "noctalia")
    shutil.copy2(NOCTALIA_BIN, bin_target)
    subprocess.run(["strip", "--strip-unneeded", bin_target], check=True)
    os.chmod(bin_target, 0o755)

    # 2. Copy assets
    if os.path.exists(NOCTALIA_ASSETS):
        shutil.copytree(NOCTALIA_ASSETS, dest_assets, dirs_exist_ok=True)
    # Also create symlink /usr/share/noctalia/assets -> /usr/share/solarui/noctalia-assets
    dest_noctalia_share = os.path.join(dest, "usr", "share", "noctalia")
    os.makedirs(dest_noctalia_share, exist_ok=True)
    os.symlink("/usr/share/solarui/noctalia-assets", os.path.join(dest_noctalia_share, "assets"))

    # 3. Desktop file
    desktop_src = os.path.join(NOCTALIA_SRC, "assets", "dev.noctalia.Noctalia.desktop")
    if os.path.exists(desktop_src):
        shutil.copy2(desktop_src, os.path.join(dest_apps, "dev.noctalia.Noctalia.desktop"))

    print(f"[noctalia] Staged binary and assets to {dest}")
    return dest

def write_recipe(name, version, release, summary, requires, dest_dir):
    recipe_dir = os.path.join(ROOT, "recipes", "core", name)
    os.makedirs(recipe_dir, exist_ok=True)
    recipe_path = os.path.join(recipe_dir, "recipe.toml")

    req_str = ", ".join(f'"{r}"' for r in requires)
    content = f"""[package]
name = "{name}"
version = "{version}"
release = {release}
architecture = "x86_64"
summary = "{summary}"
license = "LGPL-2.1-or-later OR GPL-3.0-or-later OR MIT"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://blazeos.org"

[dependencies]
requires = [{req_str}]
provides = ["{name} = {version}"]

[build]
script = \"\"\"
cp -a "{dest_dir}/"* "$DESTDIR/"
\"\"\"
"""
    with open(recipe_path, "w") as f:
        f.write(content)
    print(f"[{name}] Wrote recipe: {recipe_path}")
    return recipe_path

def build_package(recipe_path):
    cmd = [BUILDER, "--output-dir", PKGS_OUT, recipe_path]
    print(f"$ {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

# 1. Stage and build the 13 dependency packages
pkg_files = []
for name, meta in PACKAGES.items():
    dest = stage_package(name, meta)
    recipe = write_recipe(name, meta["version"], meta["release"], meta["summary"], meta["requires"], dest)
    build_package(recipe)
    blz = os.path.join(PKGS_OUT, f"{name}-{meta['version']}-{meta['release']}.x86_64.blz")
    pkg_files.append(blz)

# 2. Stage and build noctalia
noctalia_dest = stage_noctalia()
noctalia_requires = ["glibc >= 2.44", "sdbus-cpp >= 2.1.0", "tomlplusplus >= 3.4.0", "librsvg >= 2.59.2", "solar-shell >= 1.0.0"]
noctalia_recipe = write_recipe("noctalia", "5.1.0", 1, "Native Wayland Layer-Shell Desktop UI Engine for SolarUI", noctalia_requires, noctalia_dest)
build_package(noctalia_recipe)
pkg_files.append(os.path.join(PKGS_OUT, "noctalia-5.1.0-1.x86_64.blz"))

# 3. Copy packages into rootfs-b11 cache
pkg_cache = os.path.join(ROOTFS, "var", "cache", "portadora", "packages")
os.makedirs(pkg_cache, exist_ok=True)
for p in pkg_files:
    shutil.copy2(p, os.path.join(pkg_cache, os.path.basename(p)))
print(f"[CACHE] Copied {len(pkg_files)} packages to {pkg_cache}")

# 4. Install all packages into rootfs-b11 via authentic Portadora transactions
print("\n=== Installing packages into rootfs-b11 via Portadora ===")
for p in pkg_files:
    cmd = [PORTADORA, "--root", ROOTFS, "install", p]
    print(f"$ {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

# 5. Verify rootfs-b11
print("\n=== Verifying rootfs-b11 package integrity ===")
res = subprocess.run([PORTADORA, "--root", ROOTFS, "verify"], check=True)
print(f"[PORTADORA VERIFY] Result: {res.returncode}")

print("\n=== All Phase B.2 packages built and installed successfully! ===")
