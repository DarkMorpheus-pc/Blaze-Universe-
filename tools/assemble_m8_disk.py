#!/usr/bin/env python3
# ==============================================================================
# Blaze Universe — Milestone 8 Phase B.1 Disk Image Assembler
# ==============================================================================
import glob
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
    # Replace the module tree wholesale: stale .ko files from an older kernel
    # build cause "Exec format error" (struct module layout mismatch) at boot.
    shutil.rmtree(os.path.join(ROOTFS_DIR, "usr", "lib", "modules", "7.2.9"), ignore_errors=True)
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

# 3.9 Complete the systemd unit set (interim, version-checked; see the tool header)
subprocess.run([sys.executable, os.path.join(BLAZE_ROOT, "tools", "sync_systemd_units.py")],
               check=True, env={**os.environ, "BLAZE_ROOTFS": ROOTFS_DIR})

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
has_seat = False
for line in g_lines:
    parts = line.strip().split(":")
    if len(parts) >= 3 and parts[0] in ["wheel", "video", "input", "audio", "render", "users", "seat"]:
        members = [m for m in parts[3].split(",") if m] if len(parts) > 3 else []
        if "blaze" not in members:
            members.append("blaze")
        joined = ",".join(members)
        line = f"{parts[0]}:{parts[1]}:{parts[2]}:{joined}\n"
    if parts[0] == "seat":
        has_seat = True
    new_g_lines.append(line)
if not has_seat:
    new_g_lines.append("seat:x:980:blaze\n")
with open(group_file, "w") as f:
    f.writelines(new_g_lines)


shadow_file = os.path.join(etc_dir, "shadow")
# Upgraded to modern Yescrypt hashing (memory-hard, resistant to GPU cracking)
root_hash = "$y$j9T$ViTeUgA/MwzO5ZgnpCiJ3/$IiWQE6LcCEJd/TfxcOKvpigPdeD6PBcoxekynBi1zqB"
blaze_hash = "$y$j9T$ViTeUgA/MwzO5ZgnpCiJ3/$IiWQE6LcCEJd/TfxcOKvpigPdeD6PBcoxekynBi1zqB"

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
                line = f"root:{root_hash}:20740:1:365:7:::\n"
            elif parts[0] == "blaze":
                line = f"blaze:{blaze_hash}:20740:1:365:7:::\n"
        new_s_lines.append(line)
    if "root" not in shadow_users:
        new_s_lines.append(f"root:{root_hash}:20740:1:365:7:::\n")
    if "blaze" not in shadow_users:
        new_s_lines.append(f"blaze:{blaze_hash}:20740:1:365:7:::\n")
    with open(shadow_file, "w") as f:
        f.writelines(new_s_lines)
else:
    with open(shadow_file, "w") as f:
        f.write(f"root:{root_hash}:20740:1:365:7:::\n")
        f.write(f"blaze:{blaze_hash}:20740:1:365:7:::\n")

subprocess.run(f"chmod 0600 '{shadow_file}'", shell=True, check=False)

pamd_dir = os.path.join(etc_dir, "pam.d")
os.makedirs(pamd_dir, exist_ok=True)
su_pam = """#%PAM-1.0
auth       sufficient   pam_rootok.so
auth       required     pam_unix.so
account    required     pam_unix.so
password   required     pam_unix.so yescrypt shadow
session    required     pam_unix.so
"""
with open(os.path.join(pamd_dir, "su"), "w") as f:
    f.write(su_pam)
with open(os.path.join(pamd_dir, "su-l"), "w") as f:
    f.write(su_pam)

login_pam = """#%PAM-1.0
auth       sufficient   pam_rootok.so
auth       required     pam_unix.so nullok
account    required     pam_unix.so
password   required     pam_unix.so nullok yescrypt shadow
session    required     pam_unix.so
-session   optional     pam_systemd.so
"""
with open(os.path.join(pamd_dir, "login"), "w") as f:
    f.write(login_pam)
with open(os.path.join(pamd_dir, "system-local-login"), "w") as f:
    f.write(login_pam)

systemd_user_pam = """#%PAM-1.0
account    required     pam_unix.so
session    required     pam_unix.so
-session   optional     pam_systemd.so
"""
with open(os.path.join(pamd_dir, "systemd-user"), "w") as f:
    f.write(systemd_user_pam)

system_auth_pam = """#%PAM-1.0
auth       required     pam_unix.so nullok
account    required     pam_unix.so
password   required     pam_unix.so nullok yescrypt shadow
session    required     pam_unix.so
-session   optional     pam_systemd.so
"""
for pam_name in ("system-auth", "other", "passwd"):
    with open(os.path.join(pamd_dir, pam_name), "w") as f:
        f.write(system_auth_pam)

# Ensure deterministic /etc/machine-id and /var/empty (0755) for systemd & OpenSSH
machine_id_path = os.path.join(etc_dir, "machine-id")
if os.path.exists(machine_id_path):
    os.chmod(machine_id_path, 0o644)
with open(machine_id_path, "w") as f:
    f.write("b1a2e005000040008000000000000001\n")
os.chmod(machine_id_path, 0o444)
var_empty = os.path.join(ROOTFS_DIR, "var", "empty")
os.makedirs(var_empty, exist_ok=True)
os.chmod(var_empty, 0o755)

# Ensure SUID binaries
for suid_bin in ["/usr/bin/su", "/bin/su", "/usr/bin/sudo", "/usr/bin/passwd", "/sbin/unix_chkpwd", "/usr/bin/unix_chkpwd", "/usr/sbin/unix_chkpwd"]:
    full_path = ROOTFS_DIR + suid_bin
    if os.path.exists(full_path):
        subprocess.run(f"chmod 4755 '{full_path}'", shell=True, check=False)

sudoers_file = os.path.join(etc_dir, "sudoers")
if os.path.exists(sudoers_file):
    subprocess.run(f"chmod 0440 '{sudoers_file}'", shell=True, check=False)

# Set owner permissions for /home/blaze (0750 per CIS/Lynis HOME-9304)
subprocess.run(f"chown -R 1000:1000 '{ROOTFS_DIR}/home/blaze'", shell=True, check=False)
subprocess.run(f"chmod 0750 '{ROOTFS_DIR}/home/blaze'", shell=True, check=False)

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
    "portadora-0.2.0-8.x86_64.blz",
    "file-5.45-1.x86_64.blz",
    "pipewire-1.2.7-1.x86_64.blz",
    "xwayland-satellite-0.5.0-1.x86_64.blz",
    "freetype-2.13.3-1.x86_64.blz",
    "fontconfig-2.15.0-2.x86_64.blz",
    "pciutils-3.13.0-1.x86_64.blz",
    "usbutils-018-1.x86_64.blz",
    "libseat-0.9.1-1.x86_64.blz",
    "libinput-1.32.0-1.x86_64.blz",
    "wayland-1.23.0-1.x86_64.blz",
    "pixman-0.44.2-1.x86_64.blz",
    "libxkbcommon-1.7.0-1.x86_64.blz",
    "wayland-protocols-1.38-1.noarch.blz",
    "xtrans-1.5.0-1.noarch.blz",
    "noctalia-5.4.1-1.x86_64.blz",
    "solar-shell-1.0.0-2.x86_64.blz",
    "niri-26.4.0-1.x86_64.blz",
    "ncurses-6.5-1.x86_64.blz",
    "sudo-1.9.16-1.x86_64.blz",
    "fastfetch-2.69.0-1.x86_64.blz",
    "alacritty-0.17.0-1.x86_64.blz",
    "lynis-3.1.7-1.noarch.blz",
    "kbd-2.10.0-1.x86_64.blz",
    "qt6-base-6.11.2-1.x86_64.blz",
    "qt6-declarative-6.11.2-1.x86_64.blz",
    "qt6-svg-6.11.2-1.x86_64.blz",
    "quickshell-0.0.12-1.x86_64.blz",
    "quickshell-multimedia-deps-1.0.0-1.x86_64.blz",
    "ttf-material-symbols-variable-4.0.0-1.x86_64.blz",
    "xcb-util-stack-1.0.0-1.x86_64.blz",
    "sdbus-cpp-2.1.0-1.x86_64.blz",
    "tomlplusplus-3.4.0-1.x86_64.blz",
    "wireplumber-0.5.6-1.x86_64.blz",
    "librsvg-2.59.2-1.x86_64.blz",
    "libqalculate-5.5.0-1.x86_64.blz",
    "libical-3.0.18-1.x86_64.blz",
    "libsecret-0.21.4-1.x86_64.blz",
    "libsodium-1.0.20-1.x86_64.blz",
    "polkit-0.124-1.x86_64.blz",
    "tpm2-tss-4.1.3-1.x86_64.blz",
    "jemalloc-5.3.0-1.x86_64.blz",
    "libimage-codecs-1.0.0-1.x86_64.blz",
    "libaudio-codecs-1.0.0-1.x86_64.blz",
    "wl-clipboard-2.2.1-1.x86_64.blz",
    "flatpak-1.16.0-1.x86_64.blz",
    "firehub-1.9.0-1.x86_64.blz",
]

for pkg_name in AUTHENTIC_PKGS:
    pkg_file = os.path.join(BUILD_DIR, "packages", pkg_name)
    if os.path.exists(pkg_file):
        cmd = f"tar -xf '{pkg_file}' data.tar.zst -O | zstd -d -q | tar -xf - -C '{ROOTFS_DIR}'"
        subprocess.run(cmd, shell=True, check=True)
    else:
        print(f"[WARN] Package {pkg_file} not found!")

# Enforce UsrMerge /lib -> usr/lib and /usr/sbin -> bin (apparmor package extracts into lib/ and usr/sbin/)
lib_dir = os.path.join(ROOTFS_DIR, "lib")
if os.path.exists(lib_dir) and not os.path.islink(lib_dir):
    for root_w, dirs_w, files_w in os.walk(lib_dir):
        rel_w = os.path.relpath(root_w, lib_dir)
        target_w = os.path.join(ROOTFS_DIR, "usr", "lib", rel_w)
        os.makedirs(target_w, exist_ok=True)
        for f_w in files_w:
            shutil.copy2(os.path.join(root_w, f_w), os.path.join(target_w, f_w))
    shutil.rmtree(lib_dir, ignore_errors=True)
if not os.path.exists(lib_dir):
    os.symlink("usr/lib", lib_dir)

usr_sbin_dir = os.path.join(ROOTFS_DIR, "usr", "sbin")
if os.path.exists(usr_sbin_dir) and not os.path.islink(usr_sbin_dir):
    for f_w in os.listdir(usr_sbin_dir):
        src_p = os.path.join(usr_sbin_dir, f_w)
        dst_p = os.path.join(ROOTFS_DIR, "usr", "bin", f_w)
        if os.path.islink(src_p):
            if os.path.lexists(dst_p):
                os.unlink(dst_p)
            shutil.copy2(src_p, dst_p, follow_symlinks=False)
        elif os.path.isfile(src_p):
            if os.path.lexists(dst_p):
                os.unlink(dst_p)
            shutil.copy2(src_p, dst_p)
    shutil.rmtree(usr_sbin_dir, ignore_errors=True)
if not os.path.lexists(usr_sbin_dir):
    os.symlink("bin", usr_sbin_dir)

# 5.2. Install Graphics & Session Runtime Assets (only non-stub assets)
GRAPHICS_WORK = os.path.join(BUILD_DIR, "m8_graphics_work")
for gfx_pkg in ["libdrm-dest", "vulkan-loader-dest"]:
    pkg_root = os.path.join(GRAPHICS_WORK, gfx_pkg)
    if os.path.exists(pkg_root):
        subprocess.run(f"cp -rf '{pkg_root}'/* '{ROOTFS_DIR}/'", shell=True, check=False)

SESSION_WORK = os.path.join(BUILD_DIR, "m8_session_work")
for sess_pkg in ["fcft-dest"]:
    pkg_root = os.path.join(SESSION_WORK, sess_pkg)
    if os.path.exists(pkg_root):
        subprocess.run(f"cp -rf '{pkg_root}'/* '{ROOTFS_DIR}/'", shell=True, check=False)

INTEGRATION_WORK = os.path.join(BUILD_DIR, "m8_integration_work")
for integ_pkg in ["polkit-gnome-dest", "xdg-desktop-portal-dest"]:
    pkg_root = os.path.join(INTEGRATION_WORK, integ_pkg)
    if os.path.exists(pkg_root):
        subprocess.run(f"cp -rf '{pkg_root}'/* '{ROOTFS_DIR}/'", shell=True, check=False)

# 5.2.1. Ensure Mesa GBM backend (dri_gbm.so) and Gallium driver are present
gbm_dst_dir = os.path.join(ROOTFS_DIR, "usr", "lib", "gbm")
os.makedirs(gbm_dst_dir, exist_ok=True)
b11_dri_gbm = os.path.join(BUILD_DIR, "rootfs-b11", "usr", "lib", "gbm", "dri_gbm.so")
if os.path.exists(b11_dri_gbm):
    shutil.copy2(b11_dri_gbm, os.path.join(gbm_dst_dir, "dri_gbm.so"))
b11_gallium = os.path.join(BUILD_DIR, "rootfs-b11", "usr", "lib", "libgallium-26.2.3-arch3.1.so")
rootfs_gallium = os.path.join(ROOTFS_DIR, "usr", "lib", "libgallium-26.2.3-arch3.1.so")
if os.path.exists(b11_gallium) and not os.path.exists(rootfs_gallium):
    shutil.copy2(b11_gallium, rootfs_gallium)


NIRI_WORK = os.path.join(BUILD_DIR, "m9_niri_work")
for niri_pkg in ["libdisplay-info-dest", "niri-session-assets-dest"]:
    pkg_root = os.path.join(NIRI_WORK, niri_pkg)
    if os.path.exists(pkg_root):
        subprocess.run(f"cp -rf '{pkg_root}'/* '{ROOTFS_DIR}/'", shell=True, check=False)

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
Z /home/blaze 0750 blaze blaze -
d /home/blaze/.config 0755 blaze blaze -
d /home/blaze/.local 0755 blaze blaze -
d /home/blaze/.local/state 0755 blaze blaze -
d /home/blaze/.local/state/noctalia 0755 blaze blaze -
d /home/blaze/.local/state/solar 0700 blaze blaze -
d /home/blaze/.local/share 0755 blaze blaze -
d /home/blaze/.cache 0755 blaze blaze -
""")

# Configure robust autologin on tty1 for blaze user
getty_dropin_dir = os.path.join(etc_dir, "systemd", "system", "getty@tty1.service.d")
os.makedirs(getty_dropin_dir, exist_ok=True)
with open(os.path.join(getty_dropin_dir, "autologin.conf"), "w") as f:
    f.write("""[Unit]
After=systemd-modules-load.service seatd.service
Wants=seatd.service

[Service]
ExecStart=
ExecStart=-/usr/bin/agetty --autologin blaze --noclear %I $TERM
Type=idle
""")
shutil.copy2(os.path.join(getty_dropin_dir, "autologin.conf"), os.path.join(getty_dropin_dir, "override.conf"))

# Ensure serial-getty@.service is present and autologs in root
serial_unit = os.path.join(ROOTFS_DIR, "usr", "lib", "systemd", "system", "serial-getty@.service")
if not os.path.exists(serial_unit) and os.path.exists("/usr/lib/systemd/system/serial-getty@.service"):
    shutil.copy2("/usr/lib/systemd/system/serial-getty@.service", serial_unit)

serial_dropin_dir = os.path.join(etc_dir, "systemd", "system", "serial-getty@ttyS0.service.d")
os.makedirs(serial_dropin_dir, exist_ok=True)
# SECURITY: passwordless root on the serial console is only acceptable on
# developer images. Release images get a normal password prompt.
# Enable with BLAZE_DEV_AUTOLOGIN=1 (the honest test harness logs in either way).
if os.environ.get("BLAZE_DEV_AUTOLOGIN") == "1":
    with open(os.path.join(serial_dropin_dir, "autologin.conf"), "w") as f:
        f.write("""[Service]
ExecStart=
ExecStart=-/usr/bin/agetty --autologin root --noclear --keep-baud %I 115200,38400,9600 $TERM
""")
    shutil.copy2(os.path.join(serial_dropin_dir, "autologin.conf"), os.path.join(serial_dropin_dir, "override.conf"))
else:
    for stale in ("autologin.conf", "override.conf"):
        p = os.path.join(serial_dropin_dir, stale)
        if os.path.exists(p):
            os.unlink(p)


# Clean up any conflicting solar-session service (session is driven cleanly by getty@tty1 + .bash_profile)
for cleanup_path in [
    os.path.join(etc_dir, "systemd", "system", "solar-session.service"),
    os.path.join(etc_dir, "systemd", "system", "graphical.target.wants", "solar-session.service"),
    os.path.join(etc_dir, "systemd", "system", "default.target.wants", "solar-session.service"),
]:
    if os.path.exists(cleanup_path) or os.path.islink(cleanup_path):
        try:
            os.unlink(cleanup_path)
        except OSError:
            pass

default_target = os.path.join(etc_dir, "systemd", "system", "default.target")
if os.path.exists(default_target) or os.path.islink(default_target):
    try:
        os.unlink(default_target)
    except OSError:
        pass
os.symlink("/usr/lib/systemd/system/multi-user.target", default_target)





# Install and enable seatd service
seatd_unit = os.path.join(ROOTFS_DIR, "usr", "lib", "systemd", "system", "seatd.service")
os.makedirs(os.path.dirname(seatd_unit), exist_ok=True)
with open(seatd_unit, "w") as f:
    f.write("""[Unit]
Description=Seat management daemon
Documentation=man:seatd(1)
DefaultDependencies=no
Before=getty.target basic.target
Conflicts=shutdown.target

[Service]
Type=simple
ExecStart=/usr/bin/seatd -u blaze -g blaze -l info
Restart=always
RestartSec=1

[Install]
WantedBy=basic.target multi-user.target
""")

for target in ["basic.target.wants", "multi-user.target.wants"]:
    target_wants = os.path.join(etc_dir, "systemd", "system", target)
    os.makedirs(target_wants, exist_ok=True)
    seatd_link = os.path.join(target_wants, "seatd.service")
    if not os.path.exists(seatd_link):
        os.symlink("/usr/lib/systemd/system/seatd.service", seatd_link)

# Enable security services in multi-user.target
mu_wants = os.path.join(etc_dir, "systemd", "system", "multi-user.target.wants")
# Enable systemd-logind and dbus alias
for dbus_alias in ["dbus-org.freedesktop.login1.service", "dbus-org.freedesktop.locale1.service", "dbus-org.freedesktop.hostname1.service"]:
    alias_target = "systemd-logind.service" if "login1" in dbus_alias else ("systemd-localed.service" if "locale1" in dbus_alias else "systemd-hostnamed.service")
    alias_path = os.path.join(ROOTFS_DIR, "usr", "lib", "systemd", "system", dbus_alias)
    if not os.path.exists(alias_path) and not os.path.islink(alias_path):
        os.symlink(alias_target, alias_path)

logind_link = os.path.join(mu_wants, "systemd-logind.service")
if not os.path.exists(logind_link):
    os.symlink("/usr/lib/systemd/system/systemd-logind.service", logind_link)

for srv in ["nftables.service", "auditd.service", "audit-rules.service", "systemd-logind.service"]:
    srv_file = os.path.join(ROOTFS_DIR, "usr", "lib", "systemd", "system", srv)
    if os.path.exists(srv_file):
        link_path = os.path.join(mu_wants, srv)
        if not os.path.exists(link_path):
            os.symlink(f"/usr/lib/systemd/system/{srv}", link_path)

# auditd: the previous drop-in ordered auditd *after* multi-user.target while
# the unit itself runs Before=sysinit.target, creating an ordering cycle that
# made systemd silently drop auditd at every boot. Keep only a bounded start
# timeout and the modern /run PID path; the upstream ordering is correct.
auditd_dropin = os.path.join(etc_dir, "systemd", "system", "auditd.service.d")
os.makedirs(auditd_dropin, exist_ok=True)
with open(os.path.join(auditd_dropin, "override.conf"), "w") as f:
    f.write("""# Blaze Universe: bounded start, no ordering changes (see assemble_m8_disk.py)
[Service]
PIDFile=/run/auditd.pid
TimeoutStartSec=10s
""")

# AppArmor policy loader. The apparmor package provides the parser but no unit,
# so no profile was ever loaded into the kernel. Load the curated Blaze profile
# set early; one broken profile must not stop the others or the boot.
apparmor_loader = os.path.join(ROOTFS_DIR, "usr", "lib", "blaze", "apparmor-load")
os.makedirs(os.path.dirname(apparmor_loader), exist_ok=True)
with open(apparmor_loader, "w") as f:
    f.write("""#!/bin/sh
# Blaze Universe — load AppArmor profiles listed in /etc/apparmor.d/blaze.list
# (one profile file name per line). Exit status is non-zero if any failed.
set -u
[ -d /sys/kernel/security/apparmor ] || { echo "apparmor: LSM not active"; exit 0; }
list=/etc/apparmor.d/blaze.list
rc=0; n=0
while IFS= read -r p; do
    case "$p" in ''|'#'*) continue ;; esac
    if apparmor_parser --replace --write-cache --cache-loc=/var/cache/apparmor "/etc/apparmor.d/$p"; then
        n=$((n+1))
    else
        echo "apparmor: failed to load $p" >&2; rc=1
    fi
done < "$list"
echo "apparmor: loaded $n profile(s)"
exit $rc
""")
os.chmod(apparmor_loader, 0o755)
with open(os.path.join(ROOTFS_DIR, "usr", "lib", "systemd", "system", "apparmor.service"), "w") as f:
    f.write("""[Unit]
Description=Load AppArmor profiles (Blaze Sentinel)
Documentation=man:apparmor(7)
DefaultDependencies=no
After=local-fs.target systemd-journald-audit.socket
Before=sysinit.target shutdown.target
Conflicts=shutdown.target
ConditionSecurity=apparmor
RequiresMountsFor=/var/cache/apparmor

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStartPre=/usr/bin/mkdir -p /var/cache/apparmor
ExecStart=/usr/lib/blaze/apparmor-load
ExecReload=/usr/lib/blaze/apparmor-load

[Install]
WantedBy=sysinit.target
""")
aa_wants = os.path.join(etc_dir, "systemd", "system", "sysinit.target.wants")
os.makedirs(aa_wants, exist_ok=True)
aa_link = os.path.join(aa_wants, "apparmor.service")
if not os.path.lexists(aa_link):
    os.symlink("/usr/lib/systemd/system/apparmor.service", aa_link)

# 5.13.1. Configure Kernel Module Loading (VirtIO GPU & DRM KMS)
modules_load_dir = os.path.join(etc_dir, "modules-load.d")
os.makedirs(modules_load_dir, exist_ok=True)
with open(os.path.join(modules_load_dir, "virtio-gpu.conf"), "w") as f:
    f.write("""# Load VirtIO GPU and DRM helpers for Wayland display
virtio-gpu
drm
drm_kms_helper
drm_shmem_helper
virtio_dma_buf
""")

modules_service = os.path.join(ROOTFS_DIR, "usr", "lib", "systemd", "system", "systemd-modules-load.service")
os.makedirs(os.path.dirname(modules_service), exist_ok=True)
with open(modules_service, "w") as f:
    f.write("""[Unit]
Description=Load Kernel Modules
Documentation=man:systemd-modules-load.service(8) man:modules-load.d(5)
DefaultDependencies=no
Conflicts=shutdown.target
Before=sysinit.target shutdown.target
ConditionCapability=CAP_SYS_MODULE

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/lib/systemd/systemd-modules-load
TimeoutSec=90s
""")

sysinit_wants = os.path.join(etc_dir, "systemd", "system", "sysinit.target.wants")
os.makedirs(sysinit_wants, exist_ok=True)
modules_link = os.path.join(sysinit_wants, "systemd-modules-load.service")
if not os.path.exists(modules_link):
    os.symlink("/usr/lib/systemd/system/systemd-modules-load.service", modules_link)

# Write /etc/locale.conf and copy glibc locale-archive
locale_conf = os.path.join(etc_dir, "locale.conf")
with open(locale_conf, "w") as f:
    f.write("LANG=en_US.UTF-8\nLC_ALL=en_US.UTF-8\n")
if os.path.exists("/usr/lib/locale/locale-archive"):
    os.makedirs(os.path.join(ROOTFS_DIR, "usr", "lib", "locale"), exist_ok=True)
    shutil.copy2("/usr/lib/locale/locale-archive", os.path.join(ROOTFS_DIR, "usr", "lib", "locale", "locale-archive"))

# Populate /home/blaze .bash_profile for Wayland auto-launch with crash-loop protection
bash_profile_path = os.path.join(ROOTFS_DIR, "home", "blaze", ".bash_profile")
with open(bash_profile_path, "w") as f:
    f.write("""# Blaze Universe SolarUI auto-launch with crash-loop backoff & recovery fallback.
export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8
export XCURSOR_THEME=Adwaita
export XCURSOR_SIZE=24
export XDG_DATA_DIRS="${XDG_DATA_DIRS:-/usr/local/share:/usr/share}:$HOME/.local/share/flatpak/exports/share:/var/lib/flatpak/exports/share"

if [[ -z "$WAYLAND_DISPLAY" ]] && [[ "$(tty 2>/dev/null)" == "/dev/tty1" || "$(tty 2>/dev/null)" == "/dev/tty0" ]]; then
    export XDG_RUNTIME_DIR=/run/user/1000
    mkdir -p /run/user/1000 "$HOME/.local/state/solar"
    chmod 0700 /run/user/1000 "$HOME/.local/state/solar"
    ln -sf "$HOME/.local/state/solar/session.log" "$HOME/solar-session.log" 2>/dev/null || true
    if [[ ! -S /run/user/1000/bus ]]; then
        dbus-daemon --session --fork --address=unix:path=/run/user/1000/bus 2>/dev/null || true
    fi
    export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus
    modprobe virtio-gpu 2>/dev/null || true
    for _blaze_drm_wait in {1..150}; do
        compgen -G '/dev/dri/card[0-9]*' >/dev/null && break
        sleep 0.1
    done
    for _blaze_seat_wait in {1..100}; do
        [[ -S /run/seatd.sock ]] && break
        sleep 0.1
    done
    if [[ -S /run/seatd.sock ]]; then
        export LIBSEAT_BACKEND=seatd
    else
        export LIBSEAT_BACKEND=builtin
    fi

    _blaze_crash_count=0
    while [[ $_blaze_crash_count -lt 4 ]]; do
        if compgen -G '/dev/dri/card[0-9]*' >/dev/null; then
            export RUST_LOG=info
            export RUST_BACKTRACE=1
            _start_ts=$(date +%s)
            if /usr/bin/solar-session 2>&1 | tee -a /dev/ttyS0 "$HOME/.local/state/solar/session.log"; then
                break
            fi
            _elapsed=$(( $(date +%s) - _start_ts ))
            if [[ $_elapsed -gt 30 ]]; then
                _blaze_crash_count=0
            else
                _blaze_crash_count=$(( _blaze_crash_count + 1 ))
            fi
            printf '\\n[Blaze Universe] SolarUI session exited unexpectedly (%d/4). Retrying in 2s...\\n' "$_blaze_crash_count"
            sleep 2
        else
            printf '\\n[Blaze Universe] Waiting for DRM display device...\\n'
            sleep 2
            _blaze_crash_count=$(( _blaze_crash_count + 1 ))
        fi
    done
    stty sane 2>/dev/null || true
    if [[ $_blaze_crash_count -ge 4 ]]; then
        printf '\\n[BERP] SolarUI session failed 4 times consecutively. Dropping to recovery shell (run blaze-recovery for diagnostics).\\n'
    fi
fi
""")

# 5.13.2. Setup Sudoers & Permissions
sudoers_d = os.path.join(ROOTFS_DIR, "etc", "sudoers.d")
os.makedirs(sudoers_d, exist_ok=True)
sudoers_blaze = os.path.join(sudoers_d, "blaze")
if os.path.exists(sudoers_blaze):
    subprocess.run(f"chmod 0644 '{sudoers_blaze}'", shell=True, check=False)
with open(sudoers_blaze, "w") as f:
    f.write("blaze ALL=(ALL:ALL) NOPASSWD: ALL\n")
subprocess.run(f"chmod 0440 '{sudoers_blaze}'", shell=True, check=False)
sudo_bin = os.path.join(ROOTFS_DIR, "usr", "bin", "sudo")
if os.path.exists(sudo_bin):
    subprocess.run(f"chmod 4755 '{sudo_bin}'", shell=True, check=False)

# Symlink foot -> alacritty
foot_symlink = os.path.join(ROOTFS_DIR, "usr", "bin", "foot")
if not os.path.exists(foot_symlink) or os.path.islink(foot_symlink):
    try:
        os.unlink(foot_symlink)
    except OSError:
        pass
    os.symlink("alacritty", foot_symlink)

# Symlink lynis -> ../share/lynis/lynis
lynis_symlink = os.path.join(ROOTFS_DIR, "usr", "bin", "lynis")
if not os.path.exists(lynis_symlink) or os.path.islink(lynis_symlink):
    try:
        os.unlink(lynis_symlink)
    except OSError:
        pass
    os.symlink("../share/lynis/lynis", lynis_symlink)

# Setup Lynis configuration directory (/etc/lynis/default.prf & custom.prf)
lynis_etc = os.path.join(ROOTFS_DIR, "etc", "lynis")
os.makedirs(lynis_etc, exist_ok=True)
lynis_default_prf = os.path.join(ROOTFS_DIR, "usr", "share", "lynis", "default.prf")
if os.path.exists(lynis_default_prf):
    shutil.copy2(lynis_default_prf, os.path.join(lynis_etc, "default.prf"))

# Write optimized Lynis custom profile for Blaze Universe
with open(os.path.join(lynis_etc, "custom.prf"), "w") as f:
    f.write("""# Blaze Universe Custom Lynis Profile
machine-role=personal
profile-name=Blaze Universe Hardened Baseline
quick=yes
show-report-solution=yes
show-tool-tips=no
skip-test=KRNL-6000:kernel.modules_disabled
""")

# Sıkılaştırılmış limits.conf ve limits.d
limits_conf = os.path.join(etc_dir, "security", "limits.conf")
with open(limits_conf, "w") as f:
    f.write("""# Blaze Universe Security Limits
* hard core 0
* soft core 0
* hard maxlogins 10
""")

limits_d = os.path.join(etc_dir, "security", "limits.d")
os.makedirs(limits_d, exist_ok=True)
with open(os.path.join(limits_d, "10-blaze-limits.conf"), "w") as f:
    f.write("""* hard core 0
* soft core 0
* hard maxlogins 10
""")

# OpenSSH daemon hardening in /etc/ssh/sshd_config
ssh_dir = os.path.join(etc_dir, "ssh")
os.makedirs(ssh_dir, exist_ok=True)
sshd_cfg_path = os.path.join(ssh_dir, "sshd_config")
with open(sshd_cfg_path, "w") as f:
    f.write("""# Blaze Universe Hardened OpenSSH Daemon Configuration
Port 22
HostKey /etc/ssh/ssh_host_ed25519_key
HostKey /etc/ssh/ssh_host_ecdsa_key
HostKey /etc/ssh/ssh_host_rsa_key
PermitRootLogin no
MaxAuthTries 3
MaxSessions 2
LoginGraceTime 60
ClientAliveInterval 300
ClientAliveCountMax 2
X11Forwarding no
AllowAgentForwarding no
AllowTcpForwarding no
PermitTunnel no
PermitUserEnvironment no
TCPKeepAlive no
UseDNS no
Compression no
LogLevel VERBOSE
UsePAM yes
AllowGroups wheel
Banner /etc/issue.net
KexAlgorithms curve25519-sha256,curve25519-sha256@libssh.org,diffie-hellman-group16-sha512,diffie-hellman-group18-sha512
Ciphers chacha20-poly1305@openssh.com,aes256-gcm@openssh.com,aes128-gcm@openssh.com
MACs hmac-sha2-512-etm@openssh.com,hmac-sha2-256-etm@openssh.com,umac-128-etm@openssh.com
""")
os.chmod(sshd_cfg_path, 0o600)

# AppArmor profiles — 4-stage rollout (create -> complain -> refine -> enforce).
apparmor_d = os.path.join(etc_dir, "apparmor.d")
os.makedirs(apparmor_d, exist_ok=True)

with open(os.path.join(apparmor_d, "usr.lib.systemd.systemd-resolved"), "w") as f:
    f.write("""# Blaze Sentinel Profile: systemd-resolved (stage 2: complain)
abi <abi/4.0>,
include <tunables/global>
profile systemd-resolved /usr/lib/systemd/systemd-resolved flags=(complain) {
  include <abstractions/base>
  include <abstractions/nameservice>
  capability net_bind_service,
  capability setgid,
  capability setuid,
  network inet dgram,
  network inet6 dgram,
  network inet stream,
  network inet6 stream,
  network netlink raw,
  /etc/systemd/resolved.conf r,
  /etc/systemd/resolved.conf.d/{,*} r,
  /run/systemd/resolve/{,**} rw,
  /run/systemd/netif/{,**} r,
  @{PROC}/sys/net/** r,
}
""")

with open(os.path.join(apparmor_d, "usr.sbin.sshd"), "w") as f:
    f.write("""# Blaze Sentinel Profile: sshd (stage 2: complain)
abi <abi/4.0>,
include <tunables/global>
profile sshd /usr/bin/sshd flags=(complain) {
  include <abstractions/base>
  include <abstractions/authentication>
  include <abstractions/nameservice>
  capability net_bind_service,
  capability chown, capability fowner, capability kill,
  capability setgid, capability setuid, capability sys_chroot,
  capability sys_resource, capability audit_write, capability dac_override,
  network inet stream, network inet6 stream, network netlink raw,
  /etc/ssh/** r,
  /etc/issue{,.net} r,
  /etc/motd r,
  /run/sshd{,.pid} rwk,
  /var/log/{lastlog,wtmp,btmp} rwk,
  /usr/bin/bash Ux,
  /usr/lib/ssh/sshd-session Ux,
  /usr/lib/ssh/sshd-auth Ux,
}
""")

with open(os.path.join(apparmor_d, "usr.bin.blaze-sentinel"), "w") as f:
    f.write("""# Blaze Sentinel Profile: blaze-sentinel (stage 4: enforce — read-only tool)
abi <abi/4.0>,
include <tunables/global>
profile blaze-sentinel /usr/bin/blaze-sentinel flags=(enforce) {
  include <abstractions/base>
  /usr/bin/blaze-sentinel mr,
  /sys/kernel/security/{,**} r,
  /sys/module/nf_tables/{,**} r,
  /sys/fs/selinux/{,**} r,
  /sys/firmware/efi/{,**} r,
  @{PROC}/{,**} r,
  /etc/blaze/{,**} r,
  /etc/nftables.conf r,
  /etc/systemd/system/{,**} r,
  /etc/os-release r,
  /usr/lib/os-release r,
  /run/auditd.pid r,
  /run/systemd/units/{,**} r,
  /var/run/auditd.pid r,
  /var/lib/portadora/{,**} r,
}
""")

with open(os.path.join(apparmor_d, "blaze.list"), "w") as f:
    f.write("""# Profiles loaded by apparmor.service (one per line)
usr.bin.blaze-sentinel
usr.lib.systemd.systemd-resolved
usr.sbin.sshd
""")

# 5.14. Setup Fonts, Cursors, and Icons
fonts_src = "/etc/fonts"
fonts_dst = os.path.join(ROOTFS_DIR, "etc", "fonts")
if os.path.exists(fonts_src) and not os.path.exists(fonts_dst):
    os.makedirs(os.path.dirname(fonts_dst), exist_ok=True)
    shutil.copytree(fonts_src, fonts_dst, symlinks=True, dirs_exist_ok=True)

# Extract procps-ng (pgrep, pkill, ps, top, free), libnotify, and glycin (GdkPixbuf image loader) from pacman cache
for sys_pkg in [
    "procps-ng-4.0.7-1.1-x86_64_v3.pkg.tar.zst",
    "libnotify-0.8.8-1.1-x86_64_v3.pkg.tar.zst",
    "glycin-2.2.3-1.1-x86_64_v3.pkg.tar.zst",
    "glycin-gtk4-2.2.3-1.1-x86_64_v3.pkg.tar.zst",
]:
    pkg_path = os.path.join("/var/cache/pacman/pkg", sys_pkg)
    if os.path.exists(pkg_path):
        subprocess.run(f"tar -xf '{pkg_path}' -C '{ROOTFS_DIR}' usr/bin usr/lib", shell=True, check=False)

# Extract authentic cursor & icon packages from pacman cache
for icon_pkg in ["adwaita-cursors-51.0-1-any.pkg.tar.zst", "adwaita-icon-theme-51.0-1-any.pkg.tar.zst", "hicolor-icon-theme-0.18-1-any.pkg.tar.zst"]:
    pkg_path = os.path.join("/var/cache/pacman/pkg", icon_pkg)
    if os.path.exists(pkg_path):
        subprocess.run(f"tar -xf '{pkg_path}' -C '{ROOTFS_DIR}' usr/share/icons", shell=True, check=False)

# Extract Cascadia Code Nerd Font and ensure TTF fonts
nerd_pkg = "/var/cache/pacman/pkg/ttf-cascadia-code-nerd-3.5.1-2-any.pkg.tar.zst"
if os.path.exists(nerd_pkg):
    subprocess.run(f"tar -xf '{nerd_pkg}' -C '{ROOTFS_DIR}' usr/share/fonts/TTF", shell=True, check=False)

ttf_dir = os.path.join(ROOTFS_DIR, "usr", "share", "fonts", "TTF")
os.makedirs(ttf_dir, exist_ok=True)
b11_ttf = os.path.join(BUILD_DIR, "rootfs-b11", "usr", "share", "fonts", "TTF")
if os.path.exists(b11_ttf):
    for f in os.listdir(b11_ttf):
        src_f = os.path.join(b11_ttf, f)
        dst_f = os.path.join(ttf_dir, f)
        if not os.path.exists(dst_f):
            if os.path.isdir(src_f):
                shutil.copytree(src_f, dst_f, dirs_exist_ok=True)
            else:
                shutil.copy2(src_f, dst_f)

# Ensure noctalia-tabler.ttf is present in TTF directory
tabler_src = "/home/darkmorpheus/SolarUI/data/noctalia-assets/fonts/noctalia-tabler.ttf" if os.path.exists("/home/darkmorpheus/SolarUI/data/noctalia-assets/fonts/noctalia-tabler.ttf") else "/home/darkmorpheus/solarui/data/noctalia-assets/fonts/noctalia-tabler.ttf"
if os.path.exists(tabler_src) and not os.path.exists(os.path.join(ttf_dir, "noctalia-tabler.ttf")):
    shutil.copy2(tabler_src, os.path.join(ttf_dir, "noctalia-tabler.ttf"))

# Setup fontconfig cache
os.makedirs(os.path.join(ROOTFS_DIR, "var", "cache", "fontconfig"), exist_ok=True)
subprocess.run(f"chmod 0777 '{ROOTFS_DIR}/var/cache/fontconfig'", shell=True, check=False)
blaze_cache = os.path.join(ROOTFS_DIR, "home", "blaze", ".cache", "fontconfig")
os.makedirs(blaze_cache, exist_ok=True)

# Install end4-pC and caelestia quickshell provider files
solarui_src = "/home/darkmorpheus/SolarUI" if os.path.exists("/home/darkmorpheus/SolarUI") else "/home/darkmorpheus/solarui"
end4_src = os.path.join(solarui_src, "vendor", "end4-pC")
end4_dst = os.path.join(ROOTFS_DIR, "usr", "share", "quickshell", "end4-pC")
if os.path.exists(end4_src):
    os.makedirs(end4_dst, exist_ok=True)
    subprocess.run(f"rsync -a --delete --exclude='.git' '{end4_src}/' '{end4_dst}/'", shell=True, check=False)

cael_src = os.path.join(solarui_src, "vendor", "caelestia-shell")
cael_dst = os.path.join(ROOTFS_DIR, "usr", "share", "quickshell", "caelestia")
if os.path.exists(cael_src):
    os.makedirs(cael_dst, exist_ok=True)
    subprocess.run(f"rsync -a --delete --exclude='.git' '{cael_src}/' '{cael_dst}/'", shell=True, check=False)

# Copy SolarUI vector icons
solar_icons_src = "/home/darkmorpheus/SolarUI/data/icons" if os.path.exists("/home/darkmorpheus/SolarUI/data/icons") else "/home/darkmorpheus/solarui/data/icons"
if os.path.exists(solar_icons_src):
    solar_icons_dst = os.path.join(ROOTFS_DIR, "usr", "share", "solarui", "icons")
    os.makedirs(solar_icons_dst, exist_ok=True)
    shutil.copytree(solar_icons_src, solar_icons_dst, dirs_exist_ok=True)
    os.makedirs(os.path.join(ROOTFS_DIR, "usr", "share", "icons", "solarui"), exist_ok=True)
    shutil.copytree(solar_icons_src, os.path.join(ROOTFS_DIR, "usr", "share", "icons", "solarui"), dirs_exist_ok=True)

# Copy desktop configs and state from host/rootfs-b11
blaze_cfg = os.path.join(ROOTFS_DIR, "home", "blaze", ".config")
os.makedirs(blaze_cfg, exist_ok=True)
b11_cfg = os.path.join(BUILD_DIR, "rootfs-b11", "home", "blaze", ".config")
if os.path.exists(b11_cfg):
    for sub in ["caelestia", "noctalia", "quickshell"]:
        src_sub = os.path.join(b11_cfg, sub)
        dst_sub = os.path.join(blaze_cfg, sub)
        if os.path.exists(src_sub) and not os.path.exists(dst_sub):
            shutil.copytree(src_sub, dst_sub, dirs_exist_ok=True)

# Copy Noctalia State and Settings (~/.local/state/noctalia)
blaze_state = os.path.join(ROOTFS_DIR, "home", "blaze", ".local", "state", "noctalia")
os.makedirs(blaze_state, exist_ok=True)
host_noctalia_state = "/home/darkmorpheus/.local/state/noctalia"
if os.path.exists(host_noctalia_state):
    for item in ["settings.toml", "state.toml", "community-palettes", "community-templates"]:
        src_item = os.path.join(host_noctalia_state, item)
        dst_item = os.path.join(blaze_state, item)
        if os.path.exists(src_item):
            if os.path.isdir(src_item):
                shutil.copytree(src_item, dst_item, dirs_exist_ok=True)
            else:
                shutil.copy2(src_item, dst_item)

host_noctalia_cfg = "/home/darkmorpheus/.config/noctalia"
if os.path.exists(host_noctalia_cfg):
    shutil.copytree(host_noctalia_cfg, os.path.join(blaze_cfg, "noctalia"), dirs_exist_ok=True)

# Install Living Flow Noctalia wallpaper & clean calibrated settings.toml (1.0 UI scale, crisp taskbar icons)
lf_wall_src = os.path.join(solarui_src, "data", "noctalia-assets", "living-flow-wallpaper.png")
lf_wall_dst_dir = os.path.join(ROOTFS_DIR, "usr", "share", "solarui", "noctalia-assets")
os.makedirs(lf_wall_dst_dir, exist_ok=True)
if os.path.exists(lf_wall_src):
    shutil.copy2(lf_wall_src, os.path.join(lf_wall_dst_dir, "living-flow-wallpaper.png"))

with open(os.path.join(blaze_state, "settings.toml"), "w") as nf:
    nf.write("""config_version = 15

[accessibility]
ui_scale = 1.0

[bar]
order = [ "default", "taskbar" ]

    [bar.default]
    background_opacity = 0.42
    margin_edge = 5
    radius = 80

    [bar.taskbar]
    background_opacity = 0.56
    border = "outline"
    border_width = 1.0
    capsule = false
    center = [ "taskbar" ]
    concave_edge_corners = false
    contact_shadow = false
    end = [ "media", "clock", "tray", "battery" ]
    hover_highlight = true
    margin_edge = 6
    margin_ends = 110
    margin_opposite_edge = 0
    padding = 10
    panel_overlap = 1
    position = "bottom"
    radius = 22
    reserve_space = true
    scale = 1.1
    shadow = true
    start = [ "launcher" ]
    thickness = 46
    widget_spacing = 8

[widget.taskbar]
icon_scale = 1.55
item_spacing = 8.0
active_indicator_color = "#e04828"
pinned = [ "solar-welcome", "firehub", "alacritty", "solar-settings", "solar-gamezone" ]
pinned_opacity = 0.92

[lockscreen_widgets]
enabled = false
schema_version = 2
widget_order = []

[shell]
corner_radius_scale = 1.15
screen_time_enabled = true

    [shell.animation]
    speed = 1.0

    [shell.panel]
    transparency_mode = "glass"

[solarui]
clock_color_mode = "dynamic"
clock_enabled = true
clock_style = "analog_tachymeter"
dashboard_provider = "caelestia"
launcher_provider = "caelestia"
shell_engine = "noctalia"

[theme]
builtin = "Ayu"
community_palette = "Oxocarbon"
mode = "dark"
source = "builtin"

[wallpaper]
directory = "/usr/share/solarui/noctalia-assets"

    [wallpaper.default]
    path = "/usr/share/solarui/noctalia-assets/living-flow-wallpaper.png"

    [wallpaper.last]
    path = "/usr/share/solarui/noctalia-assets/living-flow-wallpaper.png"
""")

# Install Alacritty config for blaze (ColorOS 17 Living Flow frameless Obsidian terminal)
blaze_alacritty = os.path.join(blaze_cfg, "alacritty")
os.makedirs(blaze_alacritty, exist_ok=True)
with open(os.path.join(blaze_alacritty, "alacritty.toml"), "w") as f:
    f.write("""[window]
padding = { x = 18, y = 16 }
decorations = "none"
decorations_theme_variant = "Dark"
opacity = 0.96

[font]
size = 11.2

[font.normal]
family = "CaskaydiaCove Nerd Font"
style = "Regular"

[font.bold]
family = "CaskaydiaCove Nerd Font"
style = "Bold"

[font.italic]
family = "CaskaydiaCove Nerd Font"
style = "Italic"

[colors.primary]
background = "#121316"
foreground = "#e4e4e7"

[colors.cursor]
text = "#121316"
cursor = "#e54d2e"

[colors.normal]
black   = "#1c1e24"
red     = "#e54d2e"
green   = "#34d399"
yellow  = "#f59e0b"
blue    = "#93c5fd"
magenta = "#c4b5fd"
cyan    = "#99f6e4"
white   = "#d4d4d8"

[colors.bright]
black   = "#52525b"
red     = "#f87171"
green   = "#6ee7b7"
yellow  = "#fcd34d"
blue    = "#bfdbfe"
magenta = "#ddd6fe"
cyan    = "#ccfbf1"
white   = "#fafafa"
""")

# Enforce global dark mode & hicolor Living Flow icon resolution for GTK3, GTK4 & XDG
gtk_settings_ini = """[Settings]
gtk-application-prefer-dark-theme=1
gtk-theme-name=Adwaita-dark
gtk-icon-theme-name=hicolor
gtk-font-name=Sans 10.5
"""
for gtk_dir in [
    os.path.join(ROOTFS_DIR, "etc", "gtk-4.0"),
    os.path.join(ROOTFS_DIR, "etc", "gtk-3.0"),
    os.path.join(blaze_cfg, "gtk-4.0"),
    os.path.join(blaze_cfg, "gtk-3.0"),
]:
    os.makedirs(gtk_dir, exist_ok=True)
    with open(os.path.join(gtk_dir, "settings.ini"), "w") as gf:
        gf.write(gtk_settings_ini)

default_icon_dir = os.path.join(ROOTFS_DIR, "usr", "share", "icons", "default")
os.makedirs(default_icon_dir, exist_ok=True)
with open(os.path.join(default_icon_dir, "index.theme"), "w") as itf:
    itf.write("[Icon Theme]\nName=Default\nComment=Blaze Universe Living Flow Icons\nInherits=hicolor\n")

# Install Niri & SolarUI configs in all standard locations
blaze_niri_dir = os.path.join(ROOTFS_DIR, "home", "blaze", ".config", "niri")
os.makedirs(blaze_niri_dir, exist_ok=True)
blaze_solar_dir = os.path.join(ROOTFS_DIR, "home", "blaze", ".config", "solarui")
os.makedirs(blaze_solar_dir, exist_ok=True)
etc_solar_dir = os.path.join(ROOTFS_DIR, "etc", "solarui")
os.makedirs(etc_solar_dir, exist_ok=True)
usr_solar_dir = os.path.join(ROOTFS_DIR, "usr", "share", "solarui")
os.makedirs(usr_solar_dir, exist_ok=True)

solarui_src = "/home/darkmorpheus/SolarUI" if os.path.exists("/home/darkmorpheus/SolarUI") else "/home/darkmorpheus/solarui"

# Install fresh SolarUI release binaries (do NOT overwrite blaze-sentinel CLI)
for bin_name in ["solar-core", "solar-shell", "solar-session", "blaze-recovery"]:
    src_bin = os.path.join(solarui_src, "target", "release", bin_name)
    dst_bin = os.path.join(ROOTFS_DIR, "usr", "bin", bin_name)
    if os.path.exists(src_bin):
        shutil.copy2(src_bin, dst_bin)
        subprocess.run(f"chmod 0755 '{dst_bin}'", shell=True, check=False)

solar_sentinel_daemon = os.path.join(solarui_src, "target", "release", "blaze-sentinel")
if os.path.exists(solar_sentinel_daemon):
    dst_daemon = os.path.join(ROOTFS_DIR, "usr", "bin", "blaze-sentinel-daemon")
    shutil.copy2(solar_sentinel_daemon, dst_daemon)
    os.chmod(dst_daemon, 0o755)

# Install fresh BlazeOS Core Rust binaries (blaze-sentinel, blaze-continuum, portadora, solar-installer)
for core_bin in ["blaze-sentinel", "blaze-continuum", "portadora", "solar-installer"]:
    src_core = os.path.join(BLAZE_ROOT, "target", "release", core_bin)
    dst_core = os.path.join(ROOTFS_DIR, "usr", "bin", core_bin)
    if os.path.exists(src_core):
        shutil.copy2(src_core, dst_core)
        os.chmod(dst_core, 0o755)

if os.path.exists("/usr/bin/kill"):
    shutil.copy2("/usr/bin/kill", os.path.join(ROOTFS_DIR, "usr", "bin", "kill"))
    os.chmod(os.path.join(ROOTFS_DIR, "usr", "bin", "kill"), 0o755)

# Install ffmpeg + required shared libraries for live GameZone Steam HLS/MP4 trailer streaming
if os.path.exists("/usr/bin/ffmpeg"):
    shutil.copy2("/usr/bin/ffmpeg", os.path.join(ROOTFS_DIR, "usr", "bin", "ffmpeg"))
    os.chmod(os.path.join(ROOTFS_DIR, "usr", "bin", "ffmpeg"), 0o755)
    for spv_lib in glob.glob("/usr/lib/libSPIRV-Tools*.so*"):
        if os.path.isfile(spv_lib):
            shutil.copy2(spv_lib, os.path.join(ROOTFS_DIR, "usr", "lib", os.path.basename(spv_lib)))
    ldd_out = subprocess.run(["ldd", "/usr/bin/ffmpeg"], capture_output=True, text=True, check=False).stdout
    for ldd_line in ldd_out.splitlines():
        if "=>" in ldd_line:
            parts = ldd_line.split("=>")[1].strip().split()
            if parts and parts[0].startswith("/"):
                lib_src = parts[0]
                lib_dst = os.path.join(ROOTFS_DIR, "usr", "lib", os.path.basename(lib_src))
                if not os.path.exists(lib_dst) and os.path.exists(lib_src):
                    real_src = os.path.realpath(lib_src)
                    real_dst = os.path.join(ROOTFS_DIR, "usr", "lib", os.path.basename(real_src))
                    shutil.copy2(real_src, real_dst)
                    if os.path.basename(real_src) != os.path.basename(lib_src) and not os.path.lexists(lib_dst):
                        os.symlink(os.path.basename(real_src), lib_dst)

# Install brand interception library
brand_so_src = os.path.join(solarui_src, "data", "libsolar_brand.so")
if os.path.exists(brand_so_src):
    solar_lib_dir = os.path.join(ROOTFS_DIR, "usr", "lib", "solarui")
    os.makedirs(solar_lib_dir, exist_ok=True)
    shutil.copy2(brand_so_src, os.path.join(solar_lib_dir, "libsolar_brand.so"))

# Install Niri config
# Install Niri config
niri_kdl = os.path.join(solarui_src, "data", "niri.kdl")
if os.path.exists(niri_kdl):
    shutil.copy2(niri_kdl, os.path.join(blaze_niri_dir, "config.kdl"))
    shutil.copy2(niri_kdl, os.path.join(blaze_solar_dir, "niri.kdl"))
    shutil.copy2(niri_kdl, os.path.join(etc_solar_dir, "niri.kdl"))
    shutil.copy2(niri_kdl, os.path.join(usr_solar_dir, "niri.kdl"))

# Install Fastfetch Blaze Universe Logo & Configuration (Zero Arch fallback)
ff_src_dir = os.path.join(solarui_src, "data", "fastfetch")
ff_logo_src = os.path.join(ff_src_dir, "blaze-logo.txt")
ff_cfg_src = os.path.join(ff_src_dir, "config.jsonc")
if os.path.exists(ff_logo_src):
    blaze_share_dir = os.path.join(ROOTFS_DIR, "usr", "share", "blazeos")
    os.makedirs(blaze_share_dir, exist_ok=True)
    shutil.copy2(ff_logo_src, os.path.join(blaze_share_dir, "ascii-logo.txt"))
if os.path.exists(ff_cfg_src):
    for ff_dst_dir in [
        os.path.join(ROOTFS_DIR, "etc", "fastfetch"),
        os.path.join(ROOTFS_DIR, "etc", "xdg", "fastfetch"),
        os.path.join(blaze_cfg, "fastfetch"),
        os.path.join(ROOTFS_DIR, "root", ".config", "fastfetch"),
    ]:
        os.makedirs(ff_dst_dir, exist_ok=True)
        shutil.copy2(ff_cfg_src, os.path.join(ff_dst_dir, "config.jsonc"))
    ff_preset_dir = os.path.join(ROOTFS_DIR, "usr", "share", "fastfetch", "presets")
    os.makedirs(ff_preset_dir, exist_ok=True)
    shutil.copy2(ff_cfg_src, os.path.join(ff_preset_dir, "default.jsonc"))

# Generate & install ColorOS 17 Living Flow Squircle Icons, Covers & Numeric Blaze Logo
icon_gen_script = os.path.join(BLAZE_ROOT, "tools", "generate_living_flow_icons.py")
if os.path.exists(icon_gen_script):
    subprocess.run(["python3", icon_gen_script], check=True)

solar_covers_src = os.path.join(solarui_src, "data", "covers")
if os.path.exists(solar_covers_src):
    solar_covers_dst = os.path.join(ROOTFS_DIR, "usr", "share", "solarui", "covers")
    os.makedirs(solar_covers_dst, exist_ok=True)
    shutil.copytree(solar_covers_src, solar_covers_dst, dirs_exist_ok=True)
    dyn_wall = os.path.join(solar_covers_src, "xbox_dynamic.png")
    if os.path.exists(dyn_wall):
        wall_dst = os.path.join(ROOTFS_DIR, "usr", "share", "blazeos", "wallpapers")
        os.makedirs(wall_dst, exist_ok=True)
        shutil.copy2(dyn_wall, os.path.join(wall_dst, "xbox_dynamic.png"))

solar_gz_icons_src = os.path.join(solarui_src, "data", "icons", "gamezone")
if os.path.exists(solar_gz_icons_src):
    solar_icons_dst = os.path.join(ROOTFS_DIR, "usr", "share", "solarui", "icons")
    os.makedirs(solar_icons_dst, exist_ok=True)
    shutil.copytree(solar_gz_icons_src, solar_icons_dst, dirs_exist_ok=True)

# Populate gdk-pixbuf loaders.cache inside rootfs if loaders directory exists
pixbuf_loaders_dir = os.path.join(ROOTFS_DIR, "usr", "lib", "gdk-pixbuf-2.0", "2.10.0", "loaders")
if os.path.isdir(pixbuf_loaders_dir):
    q_res = subprocess.run(
        ["gdk-pixbuf-query-loaders"],
        env={**os.environ, "GDK_PIXBUF_MODULEDIR": pixbuf_loaders_dir},
        capture_output=True,
        text=True,
        check=False,
    )
    if q_res.returncode == 0 and q_res.stdout:
        fixed_cache = q_res.stdout.replace(ROOTFS_DIR, "")
        cache_out = os.path.join(ROOTFS_DIR, "usr", "lib", "gdk-pixbuf-2.0", "2.10.0", "loaders.cache")
        with open(cache_out, "w") as cf:
            cf.write(fixed_cache)

# Install Desktop Applications (.desktop files) for Noctalia, Caelestia and OmniBar
apps_dir = os.path.join(ROOTFS_DIR, "usr", "share", "applications")
os.makedirs(apps_dir, exist_ok=True)

# SolarUI Ayarları
settings_desktop = os.path.join(solarui_src, "data", "solar-settings.desktop")
if os.path.exists(settings_desktop):
    shutil.copy2(settings_desktop, os.path.join(apps_dir, "solar-settings.desktop"))

# SolarUI Karşılama
welcome_desktop = os.path.join(solarui_src, "data", "solar-welcome.desktop")
if os.path.exists(welcome_desktop):
    shutil.copy2(welcome_desktop, os.path.join(apps_dir, "solar-welcome.desktop"))

# BlazeOS Sistem Kurucusu (Solar Installer)
with open(os.path.join(apps_dir, "solar-installer.desktop"), "w") as f:
    f.write("""[Desktop Entry]
Type=Application
Name=BlazeOS Sistem Kurucusu (Solar Installer)
Comment=BlazeOS Native işletim sistemini diske kurun
Exec=/usr/bin/solar-shell installer
Icon=solar-installer
Terminal=false
Categories=System;
StartupNotify=true
StartupWMClass=solar-installer-gui
""")

# Solar GameZone
with open(os.path.join(apps_dir, "solar-gamezone.desktop"), "w") as f:
    f.write("""[Desktop Entry]
Type=Application
Name=Solar GameZone
Comment=BlazeOS Oyun Performans Merkezi, Proton-GE ve NTSYNC Yöneticisi
Exec=/usr/bin/solar-shell gamezone
Icon=solar-gamezone
Terminal=false
Categories=Game;Utility;
StartupNotify=true
StartupWMClass=solar-gamezone
""")

# Alacritty Terminal
with open(os.path.join(apps_dir, "alacritty.desktop"), "w") as f:
    f.write("""[Desktop Entry]
Type=Application
Name=Alacritty
GenericName=Terminal Emulator
Comment=A fast, cross-platform, OpenGL terminal emulator
Exec=alacritty
Icon=alacritty
Terminal=false
Categories=System;TerminalEmulator;
Keywords=terminal;shell;prompt;command;
StartupNotify=true
StartupWMClass=Alacritty
""")

subprocess.run(f"update-desktop-database '{apps_dir}'", shell=True, check=False)

# 5.15. Security Hardening Configuration (Kernel Sysctl, Audit, and Login Security)
sysctl_d = os.path.join(etc_dir, "sysctl.d")
os.makedirs(sysctl_d, exist_ok=True)
with open(os.path.join(sysctl_d, "99-blaze-hardening.conf"), "w") as f:
    f.write("""# Blaze Universe Kernel Hardening & Network Shield
kernel.kptr_restrict = 2
kernel.dmesg_restrict = 1
kernel.printk = 3 3 3 3
kernel.unprivileged_bpf_disabled = 1
kernel.core_uses_pid = 1
kernel.ctrl-alt-del = 0
kernel.sysrq = 0
kernel.randomize_va_space = 2
kernel.yama.ptrace_scope = 2
kernel.kexec_load_disabled = 1
dev.tty.ldisc_autoload = 0
kernel.perf_event_paranoid = 2
net.core.bpf_jit_harden = 2
vm.unprivileged_userfaultfd = 0
# NOTE: unprivileged user namespaces stay enabled on purpose — Flatpak,
# Chromium/Firefox sandboxes and rootless containers depend on them.
# (kernel.unprivileged_userns_clone is a Debian-only patch, absent upstream.)

# Filesystem Protections
fs.protected_hardlinks = 1
fs.protected_symlinks = 1
fs.protected_fifos = 2
fs.protected_regular = 2
fs.suid_dumpable = 0

# Network Hardening (IPv4 & IPv6)
net.ipv4.tcp_syncookies = 1
net.ipv4.conf.all.forwarding = 0
net.ipv4.conf.default.forwarding = 0
net.ipv4.conf.all.rp_filter = 1
net.ipv4.conf.default.rp_filter = 1
net.ipv4.conf.all.accept_source_route = 0
net.ipv4.conf.default.accept_source_route = 0
net.ipv4.conf.all.accept_redirects = 0
net.ipv4.conf.default.accept_redirects = 0
net.ipv4.conf.all.secure_redirects = 0
net.ipv4.conf.default.secure_redirects = 0
net.ipv4.conf.all.send_redirects = 0
net.ipv4.conf.default.send_redirects = 0
net.ipv4.conf.all.log_martians = 1
net.ipv4.conf.default.log_martians = 1
net.ipv4.icmp_echo_ignore_broadcasts = 1
net.ipv4.icmp_ignore_bogus_error_responses = 1
net.ipv4.tcp_rfc1337 = 1
net.ipv4.tcp_timestamps = 0

net.ipv6.conf.all.forwarding = 0
net.ipv6.conf.default.forwarding = 0
net.ipv6.conf.all.accept_redirects = 0
net.ipv6.conf.default.accept_redirects = 0
net.ipv6.conf.all.accept_source_route = 0
net.ipv6.conf.default.accept_source_route = 0
net.ipv6.conf.all.accept_ra = 0
net.ipv6.conf.default.accept_ra = 0
""")

# Disable core dumps via systemd coredump.conf
systemd_etc = os.path.join(etc_dir, "systemd")
os.makedirs(systemd_etc, exist_ok=True)
with open(os.path.join(systemd_etc, "coredump.conf"), "w") as f:
    f.write("""[Coredump]
Storage=none
ProcessSizeMax=0
""")

# Harden /etc/profile and /etc/bash.bashrc (umask 027, ulimit -c 0)
profile_path = os.path.join(etc_dir, "profile")
with open(profile_path, "w") as f:
    f.write("""# /etc/profile - Blaze Universe System-Wide Shell Profile
export PATH="/usr/local/sbin:/usr/local/bin:/usr/bin"
umask 027
ulimit -c 0

if [ -d /etc/profile.d ]; then
    for profile_script in /etc/profile.d/*.sh; do
        [ -r "$profile_script" ] && . "$profile_script"
    done
    unset profile_script
fi
""")

bashrc_path = os.path.join(etc_dir, "bash.bashrc")
with open(bashrc_path, "w") as f:
    f.write("""# /etc/bash.bashrc - Blaze Universe Interactive Bash Configuration
umask 027
[[ $- != *i* ]] && return
PS1='[\\u@\\h \\W]\\$ '
""")

# Harden /etc/fstab with /boot/efi, hidepid=2 on /proc, and nosuid,nodev,noexec on /tmp and /dev/shm
with open(os.path.join(etc_dir, "fstab"), "w") as f:
    f.write("""# /etc/fstab: static file system information for Blaze Universe
PARTUUID=44444444-4444-4444-4444-444444444444 / ext4 defaults,acl 0 1
LABEL=BLAZE-EFI /boot/efi vfat defaults,nofail,x-systemd.device-timeout=1s 0 2
proc /proc proc defaults,hidepid=2 0 0
tmpfs /tmp tmpfs defaults,nosuid,nodev,noexec,mode=1777 0 0
tmpfs /dev/shm tmpfs defaults,nosuid,nodev,noexec 0 0
""")
os.makedirs(os.path.join(ROOTFS_DIR, "tmp"), exist_ok=True)
os.chmod(os.path.join(ROOTFS_DIR, "tmp"), 0o1777)
os.makedirs(os.path.join(ROOTFS_DIR, "var", "tmp"), exist_ok=True)
os.chmod(os.path.join(ROOTFS_DIR, "var", "tmp"), 0o1777)

# Blacklist uncommon network protocols and DMA storage modules
modprobe_d = os.path.join(etc_dir, "modprobe.d")
os.makedirs(modprobe_d, exist_ok=True)
with open(os.path.join(modprobe_d, "blaze-hardening.conf"), "w") as f:
    f.write("""# Blaze Universe Kernel Module Hardening
install dccp /bin/false
install sctp /bin/false
install rds /bin/false
install tipc /bin/false
install firewire-core /bin/false
install firewire-ohci /bin/false
install ohci1394 /bin/false
install sbp2 /bin/false
install usb-storage /bin/false
blacklist firewire-core
blacklist firewire-ohci
blacklist ohci1394
blacklist sbp2
""")

# Restrict compiler permissions to root/owner only (0750, HRDN-7222)
import glob as _glob
for comp_pat in ["gcc", "g++", "c++", "as", "x86_64-pc-linux-gnu-*"]:
    for comp_path in _glob.glob(os.path.join(ROOTFS_DIR, "usr", "bin", comp_pat)):
        if os.path.isfile(comp_path) and not os.path.islink(comp_path):
            os.chmod(comp_path, 0o750)

# Audit Rules
audit_d = os.path.join(etc_dir, "audit", "rules.d")
os.makedirs(audit_d, exist_ok=True)
blaze_audit_rules = """-D
-b 8192
-f 1
-w /etc/passwd -p wa -k identity
-w /etc/group -p wa -k identity
-w /etc/shadow -p wa -k identity
-w /etc/sudoers -p wa -k identity
-w /etc/sudoers.d -p wa -k identity
-w /etc/login.defs -p wa -k identity
-w /etc/sysctl.d -p wa -k sysctl
-w /etc/nftables.conf -p wa -k firewall
-w /etc/issue -p wa -k system-locale
-w /etc/issue.net -p wa -k system-locale
-w /etc/security/limits.conf -p wa -k limits
-w /etc/security/limits.d -p wa -k limits
-w /etc/pam.d -p wa -k pam
-a always,exit -F arch=b64 -S init_module,finit_module,delete_module -k kernel-modules
-e 1
"""
with open(os.path.join(audit_d, "99-blaze-audit.rules"), "w") as f:
    f.write(blaze_audit_rules)
with open(os.path.join(etc_dir, "audit", "audit.rules"), "w") as f:
    f.write("## This file is automatically generated from /etc/audit/rules.d\n" + blaze_audit_rules)
os.chmod(os.path.join(etc_dir, "audit", "audit.rules"), 0o640)

# Ensure usr/lib/systemd/system/default.target points to multi-user.target
usr_default_target = os.path.join(ROOTFS_DIR, "usr", "lib", "systemd", "system", "default.target")
if os.path.lexists(usr_default_target):
    os.unlink(usr_default_target)
os.symlink("multi-user.target", usr_default_target)

# Remove any stray Qt 6.12 files so all Qt6 SONAME symlinks point consistently to 6.11.2
for stray_qt in glob.glob(os.path.join(ROOTFS_DIR, "usr", "lib", "libQt6*.6.12*")):
    try:
        os.unlink(stray_qt)
    except OSError:
        pass

# Refresh SONAME symlinks and dynamic linker cache so highest library versions win
subprocess.run(["/sbin/ldconfig", "-r", ROOTFS_DIR], check=False)

# Reconcile & Unify Portadora SQLite database with all authentic .blz packages installed on disk
if os.path.exists(db_file):
    import hashlib
    import json
    import sqlite3
    import tarfile
    import time
    import tomllib

    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    now_ts = int(time.time())

    # 1. Discover newest .blz archive for every package in build/packages/
    pkgs_dir = os.path.join(BUILD_DIR, "packages")
    newest_blz = {}
    if os.path.isdir(pkgs_dir):
        for fname in sorted(os.listdir(pkgs_dir)):
            if not fname.endswith(".blz"):
                continue
            fpath = os.path.join(pkgs_dir, fname)
            try:
                with tarfile.open(fpath, "r:*") as tf:
                    m_member = tf.extractfile("manifest.toml")
                    f_member = tf.extractfile("files.json")
                    if not m_member or not f_member:
                        continue
                    manifest = tomllib.loads(m_member.read().decode("utf-8"))
                    files_list = json.loads(f_member.read().decode("utf-8"))
                    pkg_info = manifest.get("package", {})
                    pname = pkg_info.get("name")
                    pver = str(pkg_info.get("version", "0"))
                    prel = int(pkg_info.get("release", 1))
                    if not pname:
                        continue
                    prev = newest_blz.get(pname)
                    if prev is None or (pver, prel) >= (prev[0], prev[1]):
                        newest_blz[pname] = (pver, prel, manifest, files_list)
            except Exception:
                continue

    # 2. Register every package whose payload is present in ROOTFS_DIR
    for pname, (pver, prel, manifest, files_list) in sorted(newest_blz.items()):
        non_dir_files = [fe for fe in files_list if fe.get("type") != "dir"]
        present_files = []
        for fe in files_list:
            rel_p = fe.get("path", "").lstrip("/")
            if not rel_p:
                continue
            # Account for UsrMerge (/lib -> usr/lib, /usr/sbin -> usr/bin)
            if rel_p.startswith("lib/"):
                rel_p = "usr/" + rel_p
            elif rel_p.startswith("usr/sbin/"):
                rel_p = "usr/bin/" + rel_p[len("usr/sbin/"):]
            abs_p = os.path.join(ROOTFS_DIR, rel_p)
            if os.path.lexists(abs_p):
                fe_copy = dict(fe)
                fe_copy["path"] = rel_p
                present_files.append(fe_copy)

        if non_dir_files and not any(fe.get("type") != "dir" for fe in present_files):
            continue

        pkg_meta = manifest.get("package", {})
        deps_meta = manifest.get("dependencies", {})

        cur.execute("SELECT id FROM packages WHERE name = ?", (pname,))
        row = cur.fetchone()
        if row:
            pkg_id = row[0]
            cur.execute(
                """UPDATE packages SET version=?, release=?, architecture=?, summary=?,
                   description=?, license=?, installed_size=?, install_time=? WHERE id=?""",
                (
                    pver,
                    prel,
                    pkg_meta.get("architecture", "x86_64"),
                    pkg_meta.get("summary", ""),
                    pkg_meta.get("description", ""),
                    pkg_meta.get("license", ""),
                    int(pkg_meta.get("installed_size", 0)),
                    now_ts,
                    pkg_id,
                ),
            )
            cur.execute("DELETE FROM package_provides WHERE package_id = ?", (pkg_id,))
            cur.execute("DELETE FROM package_dependencies WHERE package_id = ?", (pkg_id,))
        else:
            cur.execute(
                """INSERT INTO packages (name, version, release, architecture, summary, description, license, installed_size, install_time)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    pname,
                    pver,
                    prel,
                    pkg_meta.get("architecture", "x86_64"),
                    pkg_meta.get("summary", ""),
                    pkg_meta.get("description", ""),
                    pkg_meta.get("license", ""),
                    int(pkg_meta.get("installed_size", 0)),
                    now_ts,
                ),
            )
            pkg_id = cur.lastrowid
            cur.execute(
                """INSERT INTO transaction_history (tx_id, action, package_name, version, release, timestamp, status)
                   VALUES (?, 'INSTALL', ?, ?, ?, ?, 'SUCCESS')""",
                (f"tx-bootstrap-{pname}", pname, pver, prel, now_ts),
            )

        for prov in deps_meta.get("provides", []):
            cur.execute("INSERT INTO package_provides (package_id, capability) VALUES (?, ?)", (pkg_id, prov))
        for req in deps_meta.get("requires", []):
            cur.execute("INSERT INTO package_dependencies (package_id, requirement) VALUES (?, ?)", (pkg_id, req))

        for fe in present_files:
            rel_p = fe["path"]
            ftype = fe.get("type", "file")
            cur.execute(
                """INSERT INTO package_files (package_id, path, file_type, mode, size, sha256, symlink_target)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(path) DO UPDATE SET
                       package_id=excluded.package_id,
                       file_type=excluded.file_type,
                       mode=excluded.mode,
                       size=excluded.size,
                       sha256=excluded.sha256,
                       symlink_target=excluded.symlink_target""",
                (
                    pkg_id,
                    rel_p,
                    ftype,
                    str(fe.get("mode", "0755")),
                    int(fe.get("size", 0)),
                    fe.get("sha256"),
                    fe.get("symlink_target"),
                ),
            )

    # 3. Reconcile all tracked package_files with actual live disk state (SHA-256, size, mode, symlink_target)
    cur.execute("SELECT id, path, file_type FROM package_files")
    for row_id, rel_path, ftype in cur.fetchall():
        clean_p = rel_path.lstrip("/")
        abs_p = os.path.join(ROOTFS_DIR, clean_p)
        if not os.path.lexists(abs_p):
            cur.execute("DELETE FROM package_files WHERE id = ?", (row_id,))
            continue
        if os.path.islink(abs_p):
            target = os.readlink(abs_p)
            cur.execute("UPDATE package_files SET file_type = 'symlink', symlink_target = ?, sha256 = NULL WHERE id = ?", (target, row_id))
        elif os.path.isdir(abs_p):
            st = os.stat(abs_p)
            mode_str = f"{st.st_mode & 0o7777:04o}"
            cur.execute("UPDATE package_files SET file_type = 'dir', mode = ?, sha256 = NULL, symlink_target = NULL WHERE id = ?", (mode_str, row_id))
        elif os.path.isfile(abs_p):
            h = hashlib.sha256()
            with open(abs_p, "rb") as rf:
                while True:
                    chunk = rf.read(65536)
                    if not chunk:
                        break
                    h.update(chunk)
            st = os.stat(abs_p)
            mode_str = f"{st.st_mode & 0o7777:04o}"
            cur.execute("UPDATE package_files SET file_type = 'file', sha256 = ?, size = ?, mode = ?, symlink_target = NULL WHERE id = ?",
                        (h.hexdigest(), st.st_size, mode_str, row_id))
    conn.commit()
    conn.close()

# Login Security in /etc/login.defs
login_defs = os.path.join(etc_dir, "login.defs")
with open(login_defs, "w") as f:
    f.write("""# /etc/login.defs - Blaze Universe Shadow Password Suite Configuration
MAIL_DIR        /var/spool/mail
FAILLOG_ENAB    yes
LOG_UNKFAIL_ENAB no
LOG_OK_LOGINS   no
SYSLOG_SU_ENAB  yes
SYSLOG_SG_ENAB  yes
FTMP_FILE       /var/log/btmp
SU_NAME         su
HUSHLOGIN_FILE  .hushlogin
ENV_SUPATH      PATH=/usr/local/sbin:/usr/local/bin:/usr/bin
ENV_PATH        PATH=/usr/local/bin:/usr/bin
TTYGROUP        tty
TTYPERM         0600
ERASECHAR       0177
KILLCHAR        025
UMASK           027
PASS_MAX_DAYS   365
PASS_MIN_DAYS   1
PASS_WARN_AGE   7
UID_MIN         1000
UID_MAX         60000
SYS_UID_MIN     101
SYS_UID_MAX     999
GID_MIN         1000
GID_MAX         60000
SYS_GID_MIN     101
SYS_GID_MAX     999
LOGIN_RETRIES   5
LOGIN_TIMEOUT   60
CHFN_RESTRICT   rwh
ENCRYPT_METHOD  YESCRYPT
SHA_CRYPT_MIN_ROUNDS 5000
SHA_CRYPT_MAX_ROUNDS 10000
YESCRYPT_COST_FACTOR 7
DEFAULT_HOME    no
USERGROUPS_ENAB yes
""")

subprocess.run(f"chown -R 1000:1000 '{ROOTFS_DIR}/home/blaze'", shell=True, check=False)
subprocess.run(f"chmod 0750 '{ROOTFS_DIR}/home/blaze'", shell=True, check=False)
subprocess.run(f"fc-cache -fv '{ROOTFS_DIR}/usr/share/fonts'", shell=True, check=False)

# 5.16. Write Blaze Universe OS Release & Legal Issue Branding (Independent Native Base — Zero Arch ID_LIKE)
os_release_content = """NAME="Blaze Universe"
PRETTY_NAME="Blaze Universe 1.0 (Living Flow)"
ID=blazeos
VERSION_ID="1.0"
BUILD_ID=living-flow
ANSI_COLOR="38;2;249;115;22"
LOGO=blazeos
HOME_URL="https://github.com/DarkMorpheus-pc/Blaze-Universe-"
SUPPORT_URL="https://github.com/DarkMorpheus-pc/Blaze-Universe-/issues"
BUG_REPORT_URL="https://github.com/DarkMorpheus-pc/Blaze-Universe-/issues"
"""
with open(os.path.join(etc_dir, "os-release"), "w") as f:
    f.write(os_release_content)
os.makedirs(os.path.join(ROOTFS_DIR, "usr", "lib"), exist_ok=True)
with open(os.path.join(ROOTFS_DIR, "usr", "lib", "os-release"), "w") as f:
    f.write(os_release_content)

legal_banner = """================================================================================
Blaze Universe - Linux \\r on \\m - \\l
WARNING: Authorized access only. All system connections and activity are
monitored, logged, and subject to security policy and audit. Unauthorized
access or intrusion is strictly prohibited and subject to legal prosecution.
================================================================================
"""
with open(os.path.join(etc_dir, "issue"), "w") as f:
    f.write(legal_banner)
with open(os.path.join(etc_dir, "issue.net"), "w") as f:
    f.write(legal_banner)
with open(os.path.join(etc_dir, "motd"), "w") as f:
    f.write("""Welcome to Blaze Universe. All activities on this system are logged.
""")

# 6. Install Limine 12.x Configuration
limine_conf = """timeout: 3
default_entry: 1
graphics: yes

/Blaze Universe (Linux 7.2.9)
    protocol: linux
    kernel_path: boot():/boot/vmlinuz-blaze-7.2.9
    module_path: boot():/boot/initramfs-blaze-7.2.9.img
    cmdline: root=PARTUUID=44444444-4444-4444-4444-444444444444 rw console=ttyS0 console=tty0 lockdown=integrity

/Blaze Universe Fallback (Linux 7.2.8)
    protocol: linux
    kernel_path: boot():/boot/vmlinuz-blaze-7.2.8
    module_path: boot():/boot/initramfs-blaze-fallback.img
    cmdline: root=PARTUUID=44444444-4444-4444-4444-444444444444 rw console=ttyS0 console=tty0 lockdown=integrity

/Blaze Universe Emergency Recovery (BERP Core)
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
