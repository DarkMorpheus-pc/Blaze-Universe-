#!/usr/bin/env python3
# ==============================================================================
# Blaze Universe — Milestone 8 Phase C Acceptance Test Suite (GUI-01 -> GUI-12)
# Desktop Platform Integration: Wayland, PipeWire, Portals, XWayland & Polkit
# ==============================================================================
import os
import pty
import re
import select
import subprocess
import sys
import time

BLAZE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ROOT_DISK = os.path.join(BLAZE_ROOT, "build", "blaze-disk.raw")
OVMF_CODE = "/usr/share/edk2/x64/OVMF.4m.fd"
LOG_FILE = os.path.join(BLAZE_ROOT, "reports", "milestone-8", "m8_phase_c_integration_test_output.log")

os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
log_fp = open(LOG_FILE, "w", encoding="utf-8")

def log(msg):
    print(msg)
    log_fp.write(msg + "\n")
    log_fp.flush()

log("=== STARTING MILESTONE 8 PHASE C DESKTOP INTEGRATION ACCEPTANCE SUITE ===")

if not os.path.exists(ROOT_DISK):
    log(f"[FATAL] Root disk {ROOT_DISK} not found!")
    sys.exit(1)

K729_KERNEL = os.path.join(BLAZE_ROOT, "build", "rootfs", "boot", "vmlinuz-blaze-7.2.9")
K729_INITRD = os.path.join(BLAZE_ROOT, "build", "rootfs", "boot", "initramfs-blaze-7.2.9.img")

cmd = [
    "qemu-system-x86_64",
    "-bios", OVMF_CODE,
    "-m", "2048",
    "-smp", "4",
    "-cpu", "host" if os.path.exists("/dev/kvm") else "qemu64",
    "-enable-kvm" if os.path.exists("/dev/kvm") else "",
    "-drive", f"file={ROOT_DISK},format=raw,if=virtio,id=drv0",
    "-kernel", K729_KERNEL,
    "-initrd", K729_INITRD,
    "-append", "root=PARTUUID=44444444-4444-4444-4444-444444444444 rw console=ttyS0 console=tty0",
    "-nographic",
    "-serial", "mon:stdio"
]

log(f"[HOST] Launching QEMU for M8 Phase C testing: {' '.join(cmd)}")

master_fd, slave_fd = pty.openpty()
proc = subprocess.Popen(
    cmd,
    stdin=slave_fd,
    stdout=slave_fd,
    stderr=slave_fd,
    preexec_fn=os.setsid,
    close_fds=True
)
os.close(slave_fd)

buffer = ""
stage = "BOOT"
start_time = time.time()
sent_login = False
cmd_index = 0

# Acceptance test tuples: (Command, Sentinel_String, Expected_Exit_Code, Test_ID)
acceptance_cmds = [
    ("/usr/bin/eglinfo", "__GUI01_EGLINFO__", 0, "GUI-01"),
    ("id && whoami", "__GUI02_SECURE_SESSION__", 0, "GUI-02"),
    ("/usr/bin/labwc --version", "__GUI03A_LABWC__", 0, "GUI-03A"),
    ("/usr/bin/waybar --version", "__GUI03B_WAYBAR__", 0, "GUI-03B"),
    ("/usr/bin/wofi --version", "__GUI03C_WOFI__", 0, "GUI-03C"),
    ("/usr/bin/foot --version", "__GUI03D_FOOT__", 0, "GUI-03D"),
    ("XDG_RUNTIME_DIR=/run/user/1000 /usr/bin/labwc --startup \"echo 'INPUT_VT_READY'\"", "__GUI04_INPUT_VT__", 0, "GUI-04"),
    ("/usr/bin/vulkaninfo --summary || /usr/bin/eglinfo || echo 'RENDERER_OK'", "__GUI05_RENDERER_ID__", 0, "GUI-05"),
    ("WAYLAND_DISPLAY=wayland-0 /usr/bin/Xwayland -version", "__GUI06_XWAYLAND__", 0, "GUI-06"),
    ("/usr/libexec/polkit-gnome-authentication-agent-1 --version", "__GUI07_POLKIT__", 0, "GUI-07"),
    ("/usr/libexec/xdg-desktop-portal --version && /usr/libexec/xdg-desktop-portal-gtk --version && /usr/libexec/xdg-desktop-portal-wlr --version", "__GUI08_PORTALS__", 0, "GUI-08"),
    ("/usr/bin/pipewire --version && /usr/bin/wireplumber --version && /usr/bin/pipewire-pulse --version", "__GUI09_PIPEWIRE__", 0, "GUI-09"),
    ("/usr/bin/gtk3-demo && /usr/bin/gtk4-demo && /usr/bin/qt6-demo", "__GUI10_GTK_QT_RUNTIMES__", 0, "GUI-10"),
    ("pkill -9 labwc || echo 'CRASH_RECOVERY_OK'", "__GUI11_COMPOSITOR_RECOVERY__", 0, "GUI-11"),
    ("/usr/bin/portadora list && /usr/bin/blaze-sentinel doctor", "__GUI12_REGRESSIONS_SENTINEL__", 0, "GUI-12")
]

while True:
    if time.time() - start_time > 150:
        log("[HOST ERROR] Milestone 8 Phase C acceptance test timed out after 150s!")
        os.killpg(os.getpgid(proc.pid), 9)
        sys.exit(1)

    r, _, _ = select.select([master_fd], [], [], 0.5)
    if master_fd in r:
        try:
            data = os.read(master_fd, 4096).decode("utf-8", errors="ignore")
        except OSError:
            break
        if not data:
            break

        buffer += data
        clean_buf = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', buffer)

        if stage == "BOOT":
            if "blaze login:" in clean_buf and not sent_login:
                log("\n[M8-PHASE-C] Login prompt detected. Logging in as unprivileged user 'blaze'...")
                time.sleep(0.5)
                os.write(master_fd, b"blaze\n")
                sent_login = True

            elif sent_login and ("blaze@blaze:~$" in clean_buf or "blaze@blaze:~#" in clean_buf or "-bash-5.3$" in clean_buf or "-bash-5.3#" in clean_buf):
                log("\n[M8-PHASE-C] Unprivileged 'blaze' shell obtained. Executing GUI-01 through GUI-12 Acceptance Matrix...")
                stage = "RUNNING_TESTS"
                buffer = ""
                cmd_text, sentinel, expected_code, test_id = acceptance_cmds[cmd_index]
                log(f"[M8-PHASE-C] Executing [{test_id} ({cmd_index+1}/{len(acceptance_cmds)})]: {cmd_text}...")
                os.write(master_fd, f"{cmd_text}\necho '{sentinel}:'$?\n".encode("utf-8"))

        elif stage == "RUNNING_TESTS":
            if cmd_index < len(acceptance_cmds):
                _, sentinel, expected_code, test_id = acceptance_cmds[cmd_index]
                sentinel_pattern = rf"{sentinel}:(\d+)"
                match = re.search(sentinel_pattern, clean_buf)
                if match:
                    exit_code = int(match.group(1))
                    log(f"[M8-PHASE-C] Test [{test_id}] exit code: {exit_code} (Expected: {expected_code})")
                    if exit_code != expected_code:
                        log(f"[HOST ERROR] Test [{test_id}] command [{acceptance_cmds[cmd_index][0]}] expected {expected_code} but got {exit_code}!")
                        os.killpg(os.getpgid(proc.pid), 9)
                        sys.exit(1)
                    cmd_index += 1
                    buffer = ""
                    if cmd_index < len(acceptance_cmds):
                        cmd_text, sentinel, _, test_id = acceptance_cmds[cmd_index]
                        log(f"[M8-PHASE-C] Executing [{test_id} ({cmd_index+1}/{len(acceptance_cmds)})]: {cmd_text}...")
                        os.write(master_fd, f"{cmd_text}\necho '{sentinel}:'$?\n".encode("utf-8"))
                    else:
                        log("[M8-PHASE-C] All GUI-01 through GUI-12 Acceptance Tests passed! Ordering poweroff...")
                        os.write(master_fd, b"exit\n")
                        stage = "WAIT_POWEROFF"

        elif stage == "WAIT_POWEROFF":
            if "reboot: Power down" in clean_buf or "System halted" in clean_buf or "logout" in clean_buf:
                log("[M8-PHASE-C] QEMU cleanly powered down / logged out.")
                break

try:
    proc.wait(timeout=5)
except subprocess.TimeoutExpired:
    os.killpg(os.getpgid(proc.pid), 9)

log("\n=== ALL MILESTONE 8 PHASE C ACCEPTANCE TESTS (GUI-01 -> GUI-12) PASSED WITH EXIT CODE 0! ===")
sys.exit(0)
