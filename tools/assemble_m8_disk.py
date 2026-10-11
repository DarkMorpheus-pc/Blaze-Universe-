#!/usr/bin/env python3
# ==============================================================================
# Blaze Universe — Milestone 8 Phase B.1 Disk Image Assembler
# ==============================================================================
import os
import shutil
import subprocess
import sys

BLAZE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BUILD_DIR = os.path.join(BLAZE_ROOT, "build")
ROOTFS_DIR = os.path.abspath(os.environ.get("BLAZE_ROOTFS", os.path.join(BUILD_DIR, "rootfs")))
DISK_IMG = os.path.abspath(os.environ.get("BLAZE_DISK", os.path.join(BUILD_DIR, "blaze-disk.raw")))
ESP_IMG = os.path.join(BUILD_DIR, "esp.img")
ROOT_IMG = os.path.join(BUILD_DIR, "root.img")

print("=== Assembling Milestone 8 Phase B.1 User-Validated Wayland Session GPT Disk ===")

# 1. Verify Kernel 7.2.9 Artifacts
K729_DEST = os.path.join(BUILD_DIR, "kernel_7.2.9_work", "kernel-dest")
VMLINUZ_729 = os.path.join(K729_DEST, "boot", "vmlinuz-blaze-7.2.9")
INITRD_729 = os.path.join(K729_DEST, "boot", "initramfs-blaze-7.2.9.img")

if not os.path.exists(VMLINUZ_729):
    print(f"[ERROR] Kernel 7.2.9 binary not found at {VMLINUZ_729}!")
    sys.exit(1)

# 2. Copy Kernel 7.2.9 to Rootfs
os.makedirs(os.path.join(ROOTFS_DIR, "boot"), exist_ok=True)
os.makedirs(os.path.join(ROOTFS_DIR, "usr", "lib", "modules"), exist_ok=True)
os.makedirs(os.path.join(ROOTFS_DIR, "usr", "lib", "firmware"), exist_ok=True)
os.makedirs(os.path.join(ROOTFS_DIR, "usr", "bin"), exist_ok=True)
os.makedirs(os.path.join(ROOTFS_DIR, "root"), exist_ok=True)
os.makedirs(os.path.join(ROOTFS_DIR, "home", "blaze"), exist_ok=True)
os.makedirs(os.path.join(ROOTFS_DIR, "run", "user", "1000"), exist_ok=True)
os.makedirs(os.path.join(ROOTFS_DIR, "var", "lib", "portadora"), exist_ok=True)
subprocess.run(f"chmod 0755 '{ROOTFS_DIR}/var/lib/portadora'", shell=True, check=False)
subprocess.run(f"rm -f '{ROOTFS_DIR}/var/lib/portadora/db.sqlite-wal' '{ROOTFS_DIR}/var/lib/portadora/db.sqlite-shm'", shell=True, check=False)
db_file = os.path.join(ROOTFS_DIR, "var", "lib", "portadora", "db.sqlite")
if os.path.exists(db_file):
    subprocess.run(f"chmod 0644 '{db_file}'", shell=True, check=False)

shutil.copy2(VMLINUZ_729, os.path.join(ROOTFS_DIR, "boot", "vmlinuz-blaze-7.2.9"))
shutil.copy2(VMLINUZ_729, os.path.join(ROOTFS_DIR, "boot", "vmlinuz-blaze"))
shutil.copy2(INITRD_729, os.path.join(ROOTFS_DIR, "boot", "initramfs-blaze-7.2.9.img"))
shutil.copy2(INITRD_729, os.path.join(ROOTFS_DIR, "boot", "initramfs-blaze.img"))

# Copy modules
KMOD_DIR = os.path.join(K729_DEST, "usr", "lib", "modules")
if os.path.exists(KMOD_DIR):
    subprocess.run(f"cp -au '{KMOD_DIR}'/* '{ROOTFS_DIR}/usr/lib/modules/'", shell=True, check=False)

# 3. Preserve Kernel 7.2.8 Fallback
K728_VMLINUZ = os.path.join(BUILD_DIR, "kernel_7.2_work", "kernel-dest", "boot", "vmlinuz-linux")
K728_INITRD = os.path.join(BUILD_DIR, "kernel_7.2_work", "kernel-dest", "boot", "initramfs-linux.img")
if os.path.exists(K728_VMLINUZ):
    shutil.copy2(K728_VMLINUZ, os.path.join(ROOTFS_DIR, "boot", "vmlinuz-blaze-7.2.8"))
if os.path.exists(K728_INITRD):
    shutil.copy2(K728_INITRD, os.path.join(ROOTFS_DIR, "boot", "initramfs-blaze-fallback.img"))

# 4. Configure Unprivileged 'blaze' User Account (UID 1000, GID 1000)
etc_dir = os.path.join(ROOTFS_DIR, "etc")
os.makedirs(etc_dir, exist_ok=True)

# 4.1 Ensure DBus System Bus service symlinks
dbus_sys_dir = os.path.join(ROOTFS_DIR, "etc", "systemd", "system", "sysinit.target.wants")
os.makedirs(dbus_sys_dir, exist_ok=True)
dbus_link = os.path.join(dbus_sys_dir, "dbus.service")
if not os.path.exists(dbus_link):
    os.symlink("/usr/lib/systemd/system/dbus.service", dbus_link)

dbus_sock_dir = os.path.join(ROOTFS_DIR, "etc", "systemd", "system", "sockets.target.wants")
os.makedirs(dbus_sock_dir, exist_ok=True)
dbus_sock_link = os.path.join(dbus_sock_dir, "dbus.socket")
if not os.path.exists(dbus_sock_link):
    os.symlink("/usr/lib/systemd/system/dbus.socket", dbus_sock_link)

passwd_file = os.path.join(etc_dir, "passwd")
if os.path.exists(passwd_file):
    with open(passwd_file, "r") as f:
        passwd_content = f.read()
    if "blaze:" not in passwd_content:
        with open(passwd_file, "a") as f:
            f.write("blaze:x:1000:1000:Blaze OS Desktop User:/home/blaze:/usr/bin/bash\n")
else:
    with open(passwd_file, "w") as f:
        f.write("root:x:0:0:root:/root:/usr/bin/bash\n")
        f.write("blaze:x:1000:1000:Blaze OS Desktop User:/home/blaze:/usr/bin/bash\n")

group_file = os.path.join(etc_dir, "group")
if os.path.exists(group_file):
    with open(group_file, "r") as f:
        group_content = f.read()
    if "blaze:" not in group_content:
        with open(group_file, "a") as f:
            f.write("blaze:x:1000:\n")
else:
    with open(group_file, "w") as f:
        f.write("root:x:0:\n")
        f.write("blaze:x:1000:\n")

shadow_file = os.path.join(etc_dir, "shadow")
if os.path.exists(shadow_file):
    with open(shadow_file, "r") as f:
        shadow_content = f.read()
    if "blaze:" not in shadow_content:
        with open(shadow_file, "a") as f:
            f.write("blaze::19700:0:99999:7:::\n")
else:
    with open(shadow_file, "w") as f:
        f.write("root::19700:0:99999:7:::\n")
        f.write("blaze::19700:0:99999:7:::\n")

# Set owner permissions for /home/blaze
subprocess.run(f"chown -R 1000:1000 '{ROOTFS_DIR}/home/blaze'", shell=True, check=False)
subprocess.run(f"chmod 0755 '{ROOTFS_DIR}/home/blaze'", shell=True, check=False)

# 5. Install Firmware & Hardware Utilities
FW_WORK = os.path.join(BUILD_DIR, "firmware_work")
for fw_pkg in ["firmware-base-dest", "firmware-intel-dest", "firmware-amd-dest", "firmware-nvidia-dest", "firmware-network-dest"]:
    fw_path = os.path.join(FW_WORK, fw_pkg, "usr", "lib", "firmware")
    if os.path.exists(fw_path):
        subprocess.run(f"cp -rf '{fw_path}'/* '{ROOTFS_DIR}/usr/lib/firmware/'", shell=True, check=False)

HW_WORK = os.path.join(BUILD_DIR, "hw_utils_work")
for hw_pkg in ["pciutils-dest", "usbutils-dest"]:
    bin_path = os.path.join(HW_WORK, hw_pkg, "usr", "bin")
    if os.path.exists(bin_path):
        subprocess.run(f"cp -rf '{bin_path}'/* '{ROOTFS_DIR}/usr/bin/'", shell=True, check=False)

# 5.5. Install Blaze Sentinel Security Packages (libseccomp is native in rootfs)
SENTINEL_WORK = os.path.join(BUILD_DIR, "sentinel_work")
for sec_pkg in ["audit-dest", "apparmor-dest", "blaze-sentinel-dest"]:
    pkg_root = os.path.join(SENTINEL_WORK, sec_pkg)
    if os.path.exists(pkg_root):
        subprocess.run(f"cp -rf '{pkg_root}'/* '{ROOTFS_DIR}/'", shell=True, check=False)

# NOTE (M9 B.1.1): /usr/bin/portadora is package-managed (portadora .blz). It is never
# copied here; it is installed/upgraded only by a real Portadora transaction
# (see tools/m9_b11_apply_packages.py).

# 5.8. Install Milestone 8 Phase A Graphics Baseline Packages
GRAPHICS_WORK = os.path.join(BUILD_DIR, "m8_graphics_work")
for gfx_pkg in ["wayland-dest", "wayland-protocols-dest", "libdrm-dest", "libseat-dest", "libinput-dest", "mesa-dest", "vulkan-loader-dest", "mesa-utils-dest"]:
    pkg_root = os.path.join(GRAPHICS_WORK, gfx_pkg)
    if os.path.exists(pkg_root):
        subprocess.run(f"cp -rf '{pkg_root}'/* '{ROOTFS_DIR}/'", shell=True, check=False)

# 5.9. Install Milestone 8 Phase B.1 Wayland Session Desktop Packages (including split packages)
SESSION_WORK = os.path.join(BUILD_DIR, "m8_session_work")
for sess_pkg in ["libxkbcommon-dest", "pixman-dest", "freetype-dest", "fontconfig-dest", "fcft-dest", "wlroots-dest", "weston-dest", "labwc-dest", "foot-dest"]:
    pkg_root = os.path.join(SESSION_WORK, sess_pkg)
    if os.path.exists(pkg_root):
        subprocess.run(f"cp -rf '{pkg_root}'/* '{ROOTFS_DIR}/'", shell=True, check=False)

# 5.10. Install Milestone 8 Phase C Desktop Integration Packages
INTEGRATION_WORK = os.path.join(BUILD_DIR, "m8_integration_work")
for integ_pkg in ["xwayland-dest", "polkit-gnome-dest", "pipewire-dest", "xdg-desktop-portal-dest", "waybar-dest", "wofi-dest", "gui-runtimes-dest"]:
    pkg_root = os.path.join(INTEGRATION_WORK, integ_pkg)
    if os.path.exists(pkg_root):
        subprocess.run(f"cp -rf '{pkg_root}'/* '{ROOTFS_DIR}/'", shell=True, check=False)

# 5.11. Install Milestone 9 Phase A Native Niri Packages
NIRI_WORK = os.path.join(BUILD_DIR, "m9_niri_work")
for niri_pkg in ["libdisplay-info-dest", "xwayland-satellite-dest", "niri-dest", "niri-session-assets-dest"]:
    pkg_root = os.path.join(NIRI_WORK, niri_pkg)
    if os.path.exists(pkg_root):
        subprocess.run(f"cp -rf '{pkg_root}'/* '{ROOTFS_DIR}/'", shell=True, check=False)

# 5.12. Install Milestone 9 Phase B.1 Solar Shell Core Packages
SOLAR_WORK = os.path.join(BUILD_DIR, "m9_b1_solar_work")
for solar_pkg in ["solar-shell-dest"]:
    pkg_root = os.path.join(SOLAR_WORK, solar_pkg)
    if os.path.exists(pkg_root):
        subprocess.run(f"cp -rf '{pkg_root}'/* '{ROOTFS_DIR}/'", shell=True, check=False)

# 5.13. Run Shared Library Remediation & Write tmpfiles.d for /run/user/1000
remediate_script = os.path.join(BLAZE_ROOT, "tools", "remediate_rootfs_libs.py")
if os.path.exists(remediate_script):
    subprocess.run([sys.executable, remediate_script, ROOTFS_DIR], check=True)

tmpfiles_dir = os.path.join(ROOTFS_DIR, "usr", "lib", "tmpfiles.d")
os.makedirs(tmpfiles_dir, exist_ok=True)
with open(os.path.join(tmpfiles_dir, "blaze-user.conf"), "w") as f:
    f.write("d /run/user/1000 0700 blaze blaze -\n")

# 5.14. Setup Fontconfig & Cache Directories
if os.path.exists("/etc/fonts"):
    os.makedirs(os.path.join(ROOTFS_DIR, "etc"), exist_ok=True)
    subprocess.run(f"cp -rf /etc/fonts '{ROOTFS_DIR}/etc/'", shell=True, check=False)

os.makedirs(os.path.join(ROOTFS_DIR, "var", "cache", "fontconfig"), exist_ok=True)
subprocess.run(f"chmod 0777 '{ROOTFS_DIR}/var/cache/fontconfig'", shell=True, check=False)

blaze_cache = os.path.join(ROOTFS_DIR, "home", "blaze", ".cache", "fontconfig")
os.makedirs(blaze_cache, exist_ok=True)
subprocess.run(f"chown -R 1000:1000 '{ROOTFS_DIR}/home/blaze/.cache'", shell=True, check=False)


# 6. Install Limine 12.x Configuration
limine_conf = """timeout: 3
default_entry: 1

/BlazeOS Native (Linux 7.2.9)
    protocol: linux
    kernel_path: boot():/boot/vmlinuz-blaze-7.2.9
    module_path: boot():/boot/initramfs-blaze-7.2.9.img
    cmdline: root=PARTUUID=44444444-4444-4444-4444-444444444444 rw console=ttyS0 console=tty0

/BlazeOS Fallback (Linux 7.2.8)
    protocol: linux
    kernel_path: boot():/boot/vmlinuz-blaze-7.2.8
    module_path: boot():/boot/initramfs-blaze-fallback.img
    cmdline: root=PARTUUID=44444444-4444-4444-4444-444444444444 rw console=ttyS0 console=tty0

/BlazeOS Emergency Recovery (BERP Core)
    protocol: linux
    kernel_path: boot():/boot/vmlinuz-blaze-7.2.9
    module_path: boot():/boot/initramfs-blaze-7.2.9.img
    cmdline: root=PARTUUID=44444444-4444-4444-4444-444444444444 rw console=ttyS0 console=tty0 berp
"""

with open(os.path.join(BUILD_DIR, "limine.conf"), "w") as f:
    f.write(limine_conf)
with open(os.path.join(ROOTFS_DIR, "boot", "limine.conf"), "w") as f:
    f.write(limine_conf)

# 7. Assemble raw disk partitions
print("[DISK] Formatting ESP partition...")
ESP_SIZE = 262144 * 512
subprocess.run(["rm", "-f", ESP_IMG], check=False)
subprocess.run(["truncate", "-s", str(ESP_SIZE), ESP_IMG], check=True)
subprocess.run(["mkfs.vfat", "-F32", "-n", "BLAZE-EFI", ESP_IMG], check=True)

subprocess.run(["mmd", "-i", ESP_IMG, "::EFI", "::EFI/BOOT", "::boot"], check=True)
subprocess.run(["mcopy", "-i", ESP_IMG, "/usr/share/limine/BOOTX64.EFI", "::EFI/BOOT/BOOTX64.EFI"], check=True)
subprocess.run(["mcopy", "-i", ESP_IMG, os.path.join(BUILD_DIR, "limine.conf"), "::limine.conf"], check=True)
subprocess.run(["mcopy", "-i", ESP_IMG, os.path.join(BUILD_DIR, "limine.conf"), "::EFI/BOOT/limine.conf"], check=True)

for boot_file in ["vmlinuz-blaze-7.2.9", "initramfs-blaze-7.2.9.img", "vmlinuz-blaze-7.2.8", "initramfs-blaze-fallback.img"]:
    src_path = os.path.join(ROOTFS_DIR, "boot", boot_file)
    if os.path.exists(src_path):
        subprocess.run(["mcopy", "-i", ESP_IMG, src_path, f"::boot/{boot_file}"], check=True)

print("[DISK] Formatting Root partition (ext4)...")
ROOT_SIZE = 33288192 * 512
subprocess.run(["rm", "-f", ROOT_IMG], check=False)
subprocess.run(["truncate", "-s", str(ROOT_SIZE), ROOT_IMG], check=True)
subprocess.run(["unshare", "-r", "mkfs.ext4", "-F", "-O", "^fast_commit,^orphan_file,^metadata_csum_seed", "-L", "blaze-root", "-d", ROOTFS_DIR, ROOT_IMG], check=True)
subprocess.run(["e2fsck", "-fy", ROOT_IMG], check=False)

print("[DISK] Writing raw disk image with GPT partition table...")
subprocess.run(["rm", "-f", DISK_IMG], check=False)
subprocess.run(["truncate", "-s", "16G", DISK_IMG], check=True)

sfdisk_script = """label: gpt
label-id: 88888888-8888-8888-8888-888888888888

start=2048, size=262144, type=c12a7328-f81f-11d2-ba4b-00a0c93ec93b, name="BLAZE-EFI", uuid=11111111-1111-1111-1111-111111111111
start=264192, size=33288192, type=4f68bce3-e8cd-4db1-96e7-fbcaf984b709, name="blaze-root", uuid=44444444-4444-4444-4444-444444444444
"""
p = subprocess.Popen(["sfdisk", DISK_IMG], stdin=subprocess.PIPE, text=True)
p.communicate(sfdisk_script)

subprocess.run(["dd", f"if={ESP_IMG}", f"of={DISK_IMG}", "bs=1M", "seek=1", "conv=notrunc", "status=none"], check=True)
subprocess.run(["dd", f"if={ROOT_IMG}", f"of={DISK_IMG}", "bs=1M", "seek=129", "conv=sparse,notrunc", "status=none"], check=True)

subprocess.run(["rm", "-f", ESP_IMG, ROOT_IMG], check=False)
print("=== Milestone 8 Phase B.1 Disk Image Created Successfully! ===")
