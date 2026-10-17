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
    build_sym = os.path.join(ROOTFS_DIR, "usr", "lib", "modules", "7.2.9", "build")
    if os.path.isdir(build_sym) and not os.path.islink(build_sym):
        shutil.rmtree(build_sym, ignore_errors=True)
    subprocess.run(f"cp -a '{KMOD_DIR}'/* '{ROOTFS_DIR}/usr/lib/modules/'", shell=True, check=False)


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

# Ensure blaze is in administrative and hardware groups
with open(group_file, "r") as f:
    g_lines = f.readlines()
new_g_lines = []
for line in g_lines:
    parts = line.strip().split(":")
    if len(parts) >= 3 and parts[0] in ["wheel", "video", "input", "audio", "render", "users"]:
        members = [m for m in parts[3].split(",") if m] if len(parts) > 3 else []
        if "blaze" not in members:
            members.append("blaze")
        joined = ",".join(members)
        line = f"{parts[0]}:{parts[1]}:{parts[2]}:{joined}\n"
    new_g_lines.append(line)
with open(group_file, "w") as f:
    f.writelines(new_g_lines)

shadow_file = os.path.join(etc_dir, "shadow")
root_hash = "$6$XKu/1YObDUZKrmaJ$OScx9ToQ4z4GLvMgZbQMXjPK7ruJShfjUtQTumHhF5i9ioDQpQln2LygOAlVIXd16B03tifhtW20BYsrK3g3j0"
blaze_hash = "$6$ygn.rUshuD7ApMOM$ih3i5EnkuN23lgd5PqJr28ioIUSqrOjaTSm0tph3JdcBN3Q6at5j0SmQ.8lNvdIuCkB06e.ahOuPq57TEwwrw1"

if os.path.exists(shadow_file):
    with open(shadow_file, "r") as f:
        s_lines = f.readlines()
    new_s_lines = []
    shadow_users = set()
    for line in s_lines:
        parts = line.strip().split(":")
        if len(parts) >= 2:
            shadow_users.add(parts[0])
            if parts[0] == "root":
                parts[1] = root_hash
                line = ":".join(parts) + "\n"
            elif parts[0] == "blaze":
                parts[1] = blaze_hash
                line = ":".join(parts) + "\n"
        new_s_lines.append(line)
    if "root" not in shadow_users:
        new_s_lines.append(f"root:{root_hash}:19700:0:99999:7:::\n")
    if "blaze" not in shadow_users:
        new_s_lines.append(f"blaze:{blaze_hash}:19700:0:99999:7:::\n")
    with open(shadow_file, "w") as f:
        f.writelines(new_s_lines)
else:
    with open(shadow_file, "w") as f:
        f.write(f"root:{root_hash}:19700:0:99999:7:::\n")
        f.write(f"blaze:{blaze_hash}:19700:0:99999:7:::\n")

subprocess.run(f"chmod 0600 '{shadow_file}'", shell=True, check=False)

pamd_dir = os.path.join(etc_dir, "pam.d")
os.makedirs(pamd_dir, exist_ok=True)
su_pam = """#%PAM-1.0
auth       sufficient   pam_rootok.so
auth       required     pam_unix.so
account    required     pam_unix.so
password   required     pam_unix.so sha512 shadow
session    required     pam_unix.so
"""
with open(os.path.join(pamd_dir, "su"), "w") as f:
    f.write(su_pam)
with open(os.path.join(pamd_dir, "su-l"), "w") as f:
    f.write(su_pam)

# Ensure SUID binaries
for suid_bin in ["/usr/bin/su", "/bin/su", "/usr/bin/sudo", "/usr/bin/passwd", "/sbin/unix_chkpwd", "/usr/bin/unix_chkpwd", "/usr/sbin/unix_chkpwd"]:
    full_path = ROOTFS_DIR + suid_bin
    if os.path.exists(full_path):
        subprocess.run(f"chmod 4755 '{full_path}'", shell=True, check=False)

sudoers_file = os.path.join(etc_dir, "sudoers")
if os.path.exists(sudoers_file):
    subprocess.run(f"chmod 0440 '{sudoers_file}'", shell=True, check=False)

# Set owner permissions for /home/blaze
subprocess.run(f"chown -R 1000:1000 '{ROOTFS_DIR}/home/blaze'", shell=True, check=False)
subprocess.run(f"chmod 0755 '{ROOTFS_DIR}/home/blaze'", shell=True, check=False)

# 5. Install Firmware & Hardware Utilities
FW_WORK = os.path.join(BUILD_DIR, "firmware_work")
for fw_pkg in ["firmware-base-dest", "firmware-intel-dest", "firmware-amd-dest", "firmware-nvidia-dest", "firmware-network-dest"]:
    fw_path = os.path.join(FW_WORK, fw_pkg, "usr", "lib", "firmware")
    if os.path.exists(fw_path):
        subprocess.run(f"cp -rf '{fw_path}'/* '{ROOTFS_DIR}/usr/lib/firmware/'", shell=True, check=False)

# 5.1. Install Phase 0 Authentic Compiled Packages from build/packages/
AUTHENTIC_PKGS = [
    "libseccomp-2.5.5-2.x86_64.blz",
    "audit-4.0.2-1.x86_64.blz",
    "apparmor-4.0.3-1.x86_64.blz",
    "blaze-sentinel-0.2.0-1.x86_64.blz",
    "pipewire-1.2.7-1.x86_64.blz",
    "xwayland-satellite-0.5.0-1.x86_64.blz",
    "freetype-2.13.3-1.x86_64.blz",
    "fontconfig-2.15.0-2.x86_64.blz",
    "pciutils-3.13.0-1.x86_64.blz",
    "usbutils-018-1.x86_64.blz",
    "libseat-0.9.1-1.x86_64.blz",
    "libinput-1.26.2-1.x86_64.blz",
    "wayland-1.23.0-1.x86_64.blz",
    "pixman-0.44.2-1.x86_64.blz",
    "libxkbcommon-1.7.0-1.x86_64.blz",
    "wayland-protocols-1.38-1.noarch.blz",
    "xtrans-1.5.0-1.noarch.blz",
    "noctalia-5.1.0-1.x86_64.blz",
    "solar-shell-1.0.0-2.x86_64.blz",
    "niri-26.4.0-1.x86_64.blz",
]

for pkg_name in AUTHENTIC_PKGS:
    pkg_file = os.path.join(BUILD_DIR, "packages", pkg_name)
    if os.path.exists(pkg_file):
        cmd = f"tar -xf '{pkg_file}' data.tar.zst -O | zstd -d -q | tar -xf - -C '{ROOTFS_DIR}'"
        subprocess.run(cmd, shell=True, check=True)
    else:
        print(f"[WARN] Package {pkg_file} not found!")

# 5.2. Install Graphics & Session Runtime Assets (only non-stub assets)
GRAPHICS_WORK = os.path.join(BUILD_DIR, "m8_graphics_work")
for gfx_pkg in ["libdrm-dest", "vulkan-loader-dest"]:
    pkg_root = os.path.join(GRAPHICS_WORK, gfx_pkg)
    if os.path.exists(pkg_root):
        subprocess.run(f"cp -rf '{pkg_root}'/* '{ROOTFS_DIR}/'", shell=True, check=False)

SESSION_WORK = os.path.join(BUILD_DIR, "m8_session_work")
for sess_pkg in ["fcft-dest", "wlroots-dest"]:
    pkg_root = os.path.join(SESSION_WORK, sess_pkg)
    if os.path.exists(pkg_root):
        subprocess.run(f"cp -rf '{pkg_root}'/* '{ROOTFS_DIR}/'", shell=True, check=False)

INTEGRATION_WORK = os.path.join(BUILD_DIR, "m8_integration_work")
for integ_pkg in ["polkit-gnome-dest", "xdg-desktop-portal-dest"]:
    pkg_root = os.path.join(INTEGRATION_WORK, integ_pkg)
    if os.path.exists(pkg_root):
        subprocess.run(f"cp -rf '{pkg_root}'/* '{ROOTFS_DIR}/'", shell=True, check=False)

NIRI_WORK = os.path.join(BUILD_DIR, "m9_niri_work")
for niri_pkg in ["libdisplay-info-dest", "niri-session-assets-dest"]:
    pkg_root = os.path.join(NIRI_WORK, niri_pkg)
    if os.path.exists(pkg_root):
        subprocess.run(f"cp -rf '{pkg_root}'/* '{ROOTFS_DIR}/'", shell=True, check=False)

# Ensure aa-status in usr/bin points to authentic usr/sbin/aa-status
aa_status_bin = os.path.join(ROOTFS_DIR, "usr", "bin", "aa-status")
if os.path.exists(aa_status_bin) and not os.path.islink(aa_status_bin):
    os.remove(aa_status_bin)
if not os.path.exists(aa_status_bin) and os.path.exists(os.path.join(ROOTFS_DIR, "usr", "sbin", "aa-status")):
    os.symlink("../sbin/aa-status", aa_status_bin)

# Purge any legacy echo stubs
for stub_rel in [
    "usr/bin/Xwayland",
    "usr/bin/eglinfo",
    "usr/bin/glxinfo",
    "usr/bin/vulkaninfo",
    "usr/bin/gtk3-demo",
    "usr/bin/gtk4-demo",
    "usr/bin/qt6-demo",
    "usr/bin/waybar",
    "usr/bin/wofi",
    "usr/bin/weston",
    "usr/bin/foot",
    "usr/bin/wireplumber",
]:
    stub_path = os.path.join(ROOTFS_DIR, stub_rel)
    if os.path.exists(stub_path) and not os.path.islink(stub_path):
        try:
            with open(stub_path, "rb") as sf:
                if sf.read(4) != b"\x7fELF":
                    os.remove(stub_path)
        except Exception:
            pass

# 5.13. Run Shared Library Remediation & Write tmpfiles.d for /run/user/1000
remediate_script = os.path.join(BLAZE_ROOT, "tools", "remediate_rootfs_libs.py")
if os.path.exists(remediate_script):
    subprocess.run([sys.executable, remediate_script, ROOTFS_DIR], check=True)

tmpfiles_dir = os.path.join(ROOTFS_DIR, "usr", "lib", "tmpfiles.d")
os.makedirs(tmpfiles_dir, exist_ok=True)
with open(os.path.join(tmpfiles_dir, "blaze-user.conf"), "w") as f:
    f.write("""d /run/user/1000 0700 blaze blaze -
Z /home/blaze 0755 blaze blaze -
d /home/blaze/.config 0755 blaze blaze -
d /home/blaze/.local 0755 blaze blaze -
d /home/blaze/.local/state 0755 blaze blaze -
d /home/blaze/.local/state/noctalia 0755 blaze blaze -
d /home/blaze/.local/share 0755 blaze blaze -
d /home/blaze/.cache 0755 blaze blaze -
""")

# Ensure clean fstab (no phantom partitions causing 90s timeout)
with open(os.path.join(etc_dir, "fstab"), "w") as f:
    f.write("""# <file system> <mount point>   <type>  <options>       <dump>  <pass>
LABEL=blaze-root   /               ext4    rw,relatime     0       1
LABEL=BLAZE-EFI    /boot/efi       vfat    defaults,nofail,x-systemd.device-timeout=1s 0       2
""")

# Ensure getty@tty1 is explicitly enabled for autologin to SolarUI
for target in ["getty.target.wants", "multi-user.target.wants"]:
    wants_dir = os.path.join(etc_dir, "systemd", "system", target)
    os.makedirs(wants_dir, exist_ok=True)
    symlink_path = os.path.join(wants_dir, "getty@tty1.service")
    if not os.path.exists(symlink_path):
        os.symlink("/usr/lib/systemd/system/getty@.service", symlink_path)

# 5.14. Setup Fontconfig & Cache Directories
fonts_src = "/etc/fonts"
fonts_dst = os.path.join(ROOTFS_DIR, "etc", "fonts")
if os.path.exists(fonts_src) and not os.path.exists(fonts_dst):
    os.makedirs(os.path.dirname(fonts_dst), exist_ok=True)
    shutil.copytree(fonts_src, fonts_dst, symlinks=True, dirs_exist_ok=True)



os.makedirs(os.path.join(ROOTFS_DIR, "var", "cache", "fontconfig"), exist_ok=True)
subprocess.run(f"chmod 0777 '{ROOTFS_DIR}/var/cache/fontconfig'", shell=True, check=False)

blaze_cache = os.path.join(ROOTFS_DIR, "home", "blaze", ".cache", "fontconfig")
os.makedirs(blaze_cache, exist_ok=True)
subprocess.run(f"chown -R 1000:1000 '{ROOTFS_DIR}/home/blaze/.cache'", shell=True, check=False)

blaze_niri_dir = os.path.join(ROOTFS_DIR, "home", "blaze", ".config", "niri")
os.makedirs(blaze_niri_dir, exist_ok=True)
if os.path.exists("/home/darkmorpheus/solarui/data/niri.kdl"):
    shutil.copy2("/home/darkmorpheus/solarui/data/niri.kdl", os.path.join(blaze_niri_dir, "config.kdl"))
subprocess.run(f"chown -R 1000:1000 '{ROOTFS_DIR}/home/blaze/.config'", shell=True, check=False)


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
