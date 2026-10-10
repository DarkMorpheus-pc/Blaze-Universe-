#!/usr/bin/env python3
# ==============================================================================
# Blaze Universe — Milestone 6 Disk Image Assembler
# ==============================================================================
import os
import shutil
import subprocess
import sys

BLAZE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BUILD_DIR = os.path.join(BLAZE_ROOT, "build")
ROOTFS_DIR = os.path.join(BUILD_DIR, "rootfs")
DISK_IMG = os.path.join(BUILD_DIR, "blaze-disk.raw")
ESP_IMG = os.path.join(BUILD_DIR, "esp.img")
ROOT_IMG = os.path.join(BUILD_DIR, "root.img")

print("=== Assembling Milestone 6 Hardware-Enabled GPT Boot Disk ===")

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

shutil.copy2(VMLINUZ_729, os.path.join(ROOTFS_DIR, "boot", "vmlinuz-blaze-7.2.9"))
shutil.copy2(VMLINUZ_729, os.path.join(ROOTFS_DIR, "boot", "vmlinuz-blaze"))
shutil.copy2(INITRD_729, os.path.join(ROOTFS_DIR, "boot", "initramfs-blaze-7.2.9.img"))
shutil.copy2(INITRD_729, os.path.join(ROOTFS_DIR, "boot", "initramfs-blaze.img"))

# Copy modules
KMOD_DIR = os.path.join(K729_DEST, "usr", "lib", "modules")
if os.path.exists(KMOD_DIR):
    for item in os.listdir(KMOD_DIR):
        src = os.path.join(KMOD_DIR, item)
        dst = os.path.join(ROOTFS_DIR, "usr", "lib", "modules", item)
        if os.path.isdir(src):
            shutil.rmtree(dst, ignore_errors=True)
            shutil.copytree(src, dst)

# 3. Preserve Kernel 7.2.8 Fallback if available
K728_VMLINUZ = os.path.join(BUILD_DIR, "kernel_7.2_work", "kernel-dest", "boot", "vmlinuz-linux")
K728_INITRD = os.path.join(BUILD_DIR, "kernel_7.2_work", "kernel-dest", "boot", "initramfs-linux.img")
if os.path.exists(K728_VMLINUZ):
    shutil.copy2(K728_VMLINUZ, os.path.join(ROOTFS_DIR, "boot", "vmlinuz-blaze-7.2.8"))
if os.path.exists(K728_INITRD):
    shutil.copy2(K728_INITRD, os.path.join(ROOTFS_DIR, "boot", "initramfs-blaze-fallback.img"))

# 4. Install Firmware Directories
FW_WORK = os.path.join(BUILD_DIR, "firmware_work")
for fw_pkg in ["firmware-base-dest", "firmware-intel-dest", "firmware-amd-dest", "firmware-nvidia-dest", "firmware-network-dest"]:
    fw_path = os.path.join(FW_WORK, fw_pkg, "usr", "lib", "firmware")
    if os.path.exists(fw_path):
        subprocess.run(f"cp -rf '{fw_path}'/* '{ROOTFS_DIR}/usr/lib/firmware/'", shell=True, check=False)

# 5. Install Hardware Utilities
HW_WORK = os.path.join(BUILD_DIR, "hw_utils_work")
for hw_pkg in ["pciutils-dest", "usbutils-dest"]:
    bin_path = os.path.join(HW_WORK, hw_pkg, "usr", "bin")
    if os.path.exists(bin_path):
        subprocess.run(f"cp -rf '{bin_path}'/* '{ROOTFS_DIR}/usr/bin/'", shell=True, check=False)

# 5.5. Install Blaze Sentinel Security Packages
SENTINEL_WORK = os.path.join(BUILD_DIR, "sentinel_work")
for sec_pkg in ["libseccomp-dest", "audit-dest", "apparmor-dest", "blaze-sentinel-dest"]:
    pkg_root = os.path.join(SENTINEL_WORK, sec_pkg)
    if os.path.exists(pkg_root):
        subprocess.run(f"cp -rf '{pkg_root}'/* '{ROOTFS_DIR}/'", shell=True, check=False)

# 6. Install Guest Test Script
shutil.copy2(os.path.join(BLAZE_ROOT, "tools", "run_m6_tests.sh"), os.path.join(ROOTFS_DIR, "root", "run_m6_tests.sh"))
os.chmod(os.path.join(ROOTFS_DIR, "root", "run_m6_tests.sh"), 0o755)

# 7. Write Limine 12.x Dual-Kernel & BERP Configuration
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

# 8. Assemble raw disk partitions
print("[DISK] Formatting ESP partition...")
ESP_SIZE = 262144 * 512
subprocess.run(["rm", "-f", ESP_IMG], check=False)
subprocess.run(["truncate", "-s", str(ESP_SIZE), ESP_IMG], check=True)
subprocess.run(["mkfs.vfat", "-F32", "-n", "BLAZE-EFI", ESP_IMG], check=True)

subprocess.run(["mmd", "-i", ESP_IMG, "::EFI", "::EFI/BOOT", "::boot"], check=True)
subprocess.run(["mcopy", "-i", ESP_IMG, "/usr/share/limine/BOOTX64.EFI", "::EFI/BOOT/BOOTX64.EFI"], check=True)
subprocess.run(["mcopy", "-i", ESP_IMG, os.path.join(BUILD_DIR, "limine.conf"), "::limine.conf"], check=True)
subprocess.run(["mcopy", "-i", ESP_IMG, os.path.join(BUILD_DIR, "limine.conf"), "::EFI/BOOT/limine.conf"], check=True)

# Copy kernel & initramfs binaries to ESP image for Limine boot access
for boot_file in ["vmlinuz-blaze-7.2.9", "initramfs-blaze-7.2.9.img", "vmlinuz-blaze-7.2.8", "initramfs-blaze-fallback.img"]:
    src_path = os.path.join(ROOTFS_DIR, "boot", boot_file)
    if os.path.exists(src_path):
        subprocess.run(["mcopy", "-i", ESP_IMG, src_path, f"::boot/{boot_file}"], check=True)

print("[DISK] Formatting Root partition (ext4)...")
ROOT_SIZE = 33288192 * 512
subprocess.run(["rm", "-f", ROOT_IMG], check=False)
subprocess.run(["truncate", "-s", str(ROOT_SIZE), ROOT_IMG], check=True)
subprocess.run(["unshare", "-r", "mkfs.ext4", "-F", "-L", "blaze-root", "-d", ROOTFS_DIR, ROOT_IMG], check=True)

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
subprocess.run(["dd", f"if={ROOT_IMG}", f"of={DISK_IMG}", "bs=1M", "seek=129", "conv=notrunc,sparse", "status=none"], check=True)

subprocess.run(["rm", "-f", ESP_IMG, ROOT_IMG], check=False)
print("=== Milestone 6 Disk Image Created Successfully! ===")
