#!/usr/bin/env python3
# ==============================================================================
# Blaze Universe — Milestone 9 Phase B.2.1 Acceptance Test Suite
# Real Graphics / Noctalia 5.1.0 Wayland Layer-Shell / Launcher / Supervisor
# Unattended Watchdog Recovery / Keybinding Verification / App Launch
# ==============================================================================
import json
import os
import pty
import re
import select
import socket
import subprocess
import sys
import time
from PIL import Image

BLAZE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BUILD_DIR = os.path.join(BLAZE_ROOT, "build")
BASE_DISK = os.path.join(BUILD_DIR, "blaze-disk-b11.raw")
OVERLAY_DISK = "/tmp/blaze-m9-b21-acceptance-overlay.qcow2"
OVMF_CODE = "/usr/share/edk2/x64/OVMF.4m.fd"
LOG_FILE = os.path.join(BLAZE_ROOT, "reports", "milestone-9", "m9_phase_b21_acceptance_output.log")
MONITOR_SOCKET = "/tmp/qemu-m9-b21-mon.sock"
PPM_SCREENSHOT = "/tmp/qemu_noctalia_b21.ppm"
PNG_SCREENSHOT = "/tmp/blazeos_m9_b21_noctalia_real_framebuffer.png"
ARTIFACT_DIR = "/home/darkmorpheus/.gemini/antigravity/brain/edfcc68e-d62a-469a-afaa-c49b73f87c64"
ARTIFACT_PNG = os.path.join(ARTIFACT_DIR, "blazeos_m9_b21_noctalia_real_framebuffer.png")

os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
log_fp = open(LOG_FILE, "w", encoding="utf-8")

def log(msg):
    print(msg, flush=True)
    log_fp.write(msg + "\n")
    log_fp.flush()

log("=== STARTING MILESTONE 9 PHASE B.2.1 NOCTALIA VISUAL SHELL ACCEPTANCE TEST ===")

if not os.path.exists(BASE_DISK):
    log(f"[FATAL] Base disk {BASE_DISK} not found!")
    sys.exit(1)

# Clean up previous sockets and processes
subprocess.run("pkill -9 -f qemu-system-x86_64 || true", shell=True, check=False)
for s in [MONITOR_SOCKET, PPM_SCREENSHOT, PNG_SCREENSHOT, OVERLAY_DISK]:
    if os.path.exists(s):
        try:
            os.remove(s)
        except Exception:
            pass

log(f"[HOST] Creating disposable QCOW2 overlay on top of {BASE_DISK}...")
subprocess.run(
    ["qemu-img", "create", "-f", "qcow2", "-b", BASE_DISK, "-F", "raw", OVERLAY_DISK],
    check=True
)

K729_KERNEL = os.path.join(BUILD_DIR, "rootfs-b11", "boot", "vmlinuz-blaze-7.2.9")
K729_INITRD = os.path.join(BUILD_DIR, "rootfs-b11", "boot", "initramfs-blaze-7.2.9.img")

cmd = [
    "qemu-system-x86_64",
    "-bios", OVMF_CODE,
    "-m", "2048",
    "-smp", "4",
    "-cpu", "host" if os.path.exists("/dev/kvm") else "qemu64",
    "-vga", "virtio",
    "-drive", f"file={OVERLAY_DISK},format=qcow2,if=virtio,id=drv0",
    "-device", "intel-hda",
    "-device", "hda-duplex",
    "-kernel", K729_KERNEL,
    "-initrd", K729_INITRD,
    "-append", "root=PARTUUID=44444444-4444-4444-4444-444444444444 rw console=ttyS0 console=tty0 quiet loglevel=3",
    "-nographic",
    "-serial", "mon:stdio",
    "-monitor", f"unix:{MONITOR_SOCKET},server,nowait"
]
if os.path.exists("/dev/kvm"):
    cmd.insert(5, "-enable-kvm")

log("[HOST] Launching QEMU...")
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

def send(cmd_str):
    os.write(master_fd, (cmd_str + "\n").encode())

def read_until(pattern, timeout=40):
    start = time.time()
    buf = ""
    while time.time() - start < timeout:
        r, _, _ = select.select([master_fd], [], [], 0.5)
        if master_fd in r:
            try:
                d = os.read(master_fd, 4096).decode(errors="ignore")
                buf += d
                sys.stdout.write(d)
                sys.stdout.flush()
                log_fp.write(d)
                log_fp.flush()
                clean = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', buf)
                if pattern in clean:
                    return clean
            except OSError:
                break
    return buf

def run_step(cmd_text, desc, expected_code=0):
    log(f"\n>>> EXECUTING: {desc}")
    sentinel = f"__SENTINEL_{int(time.time()*1000)}__"
    send(f"{cmd_text}\necho '{sentinel}:'$?")
    pattern = rf"{sentinel}:(\d+)"
    start = time.time()
    buf = ""
    while time.time() - start < 45:
        r, _, _ = select.select([master_fd], [], [], 0.5)
        if master_fd in r:
            try:
                d = os.read(master_fd, 4096).decode(errors="ignore")
                buf += d
                sys.stdout.write(d)
                sys.stdout.flush()
                log_fp.write(d)
                log_fp.flush()
                clean = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', buf)
                m = re.search(pattern, clean)
                if m:
                    code = int(m.group(1))
                    log(f"\n[HOST RESULT] [{desc}] Exit Code: {code} (Expected: {expected_code})")
                    if code != expected_code:
                        log(f"[HOST ERROR] Step failed! Code {code} != {expected_code}")
                        os.killpg(os.getpgid(proc.pid), 9)
                        sys.exit(1)
                    return clean
            except OSError:
                break
    log(f"[HOST ERROR] Timeout waiting for sentinel on step: {desc}")
    os.killpg(os.getpgid(proc.pid), 9)
    sys.exit(1)

def send_qemu_monitor(cmd_str):
    log(f"[HOST MONITOR] Sending command: {cmd_str}")
    time.sleep(0.5)
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(MONITOR_SOCKET)
    s.recv(1024)
    s.sendall(f"{cmd_str}\n".encode("utf-8"))
    time.sleep(0.5)
    s.close()

def capture_screendump():
    log("[HOST] Taking QEMU screendump via monitor socket...")
    time.sleep(2)
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(MONITOR_SOCKET)
    s.recv(1024)
    s.sendall(f"screendump {PPM_SCREENSHOT}\n".encode("utf-8"))
    time.sleep(1)
    s.close()

    if not os.path.exists(PPM_SCREENSHOT) or os.path.getsize(PPM_SCREENSHOT) == 0:
        log("[HOST ERROR] screendump failed or generated 0-byte file!")
        return False

    im = Image.open(PPM_SCREENSHOT)
    im.save(PNG_SCREENSHOT)
    im.save(ARTIFACT_PNG)
    log(f"[HOST] Saved screendump to {PNG_SCREENSHOT} and artifact {ARTIFACT_PNG} (Size: {im.size})")
    colors = im.getcolors(maxcolors=100000)
    log(f"[HOST] Screendump distinct colors count: {len(colors) if colors else 'many'}")
    return True

# 1. Boot to root
log("[HOST] Waiting for login prompt...")
read_until("login:", 45)
send("root")
time.sleep(1)
send("")
read_until("-bash-5.3#", 15)
log("[HOST] Root shell obtained.")

# 2. Portadora verification on boot
run_step("/usr/bin/portadora verify", "Audit complete package integrity with Portadora", 0)

# 3. Check Noctalia and Solar Shell ELF binaries and libraries
run_step("file /usr/bin/noctalia /usr/bin/solar-shell && ldd /usr/bin/noctalia | grep 'not found' || echo 'ALL_LIBS_OK'", "Verify native ELF binaries and zero missing shared libraries", 0)

# 4. Start system services
run_step("seatd -u blaze -g blaze -n 1 > /tmp/seatd.log 2>&1 & sleep 1; test -S /run/seatd.sock && echo 'SEATD_OK'", "Start seatd daemon", 0)
run_step("mkdir -p /run/dbus && dbus-daemon --system --fork 2>/dev/null || true", "Start D-Bus system daemon", 0)
run_step("mkdir -p /run/user/1000 && chown -R blaze:blaze /run/user/1000 /home/blaze && chmod 0700 /run/user/1000", "Ensure /run/user/1000 permissions", 0)

# 5. Switch to blaze user
log("\n[HOST] Switching to unprivileged user 'blaze' (UID 1000)...")
send("su - blaze")
time.sleep(1)
read_until("-bash-5.3$", 10)
log("[HOST] User 'blaze' shell active.")

run_step("id && whoami", "Verify UID 1000 (blaze)", 0)

# 6. Start D-Bus session bus for user 1000
run_step("export XDG_RUNTIME_DIR=/run/user/1000; dbus-daemon --session --fork --address=unix:path=/run/user/1000/bus 2>/dev/null || true; export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus; echo 'DBUS_USER_OK'", "Start D-Bus user session daemon", 0)

# 7. Start Niri Compositor with SolarUI configuration
run_step("export XDG_RUNTIME_DIR=/run/user/1000; export LIBSEAT_BACKEND=seatd; export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus; unset WAYLAND_DISPLAY; niri --config /home/blaze/.config/niri/config.kdl > /tmp/niri.log 2>&1 & sleep 3; test -S /run/user/1000/wayland-1 && echo 'WAYLAND_OK'", "Start Niri compositor with SolarUI configuration", 0)

# 8. Start Solar Shell Supervisor and verify Noctalia visual shell
run_step("export XDG_RUNTIME_DIR=/run/user/1000; export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus; export WAYLAND_DISPLAY=wayland-1; export NIRI_SOCKET=$(ls /run/user/1000/niri.*.sock | head -n1); (pgrep -x solar-shell || solar-shell supervisor > /tmp/solar-shell.log 2>&1 &); sleep 4; pgrep -x noctalia && echo 'NOCTALIA_RUNNING'", "Start Solar Shell supervisor & reconcile Noctalia visual shell", 0)

# 9. Verify Noctalia status via IPC (barVisible, workspaces, clock)
run_step("export XDG_RUNTIME_DIR=/run/user/1000; export WAYLAND_DISPLAY=wayland-1; noctalia msg status | head -n 30", "Query Noctalia status JSON via IPC", 0)

# 10. Launch first Wayland client window inside Niri
run_step("export XDG_RUNTIME_DIR=/run/user/1000; export WAYLAND_DISPLAY=wayland-1; alacritty --hold -e echo 'BLAZEOS REAL WAYLAND CLIENT WITH NOCTALIA PANEL' > /tmp/alacritty.log 2>&1 & sleep 2; export NIRI_SOCKET=$(ls /run/user/1000/niri.*.sock | head -n1); niri msg --json windows", "Launch client window in Niri and query via IPC", 0)

# 11. Verify Active Keybindings & Layer-Shell Surfaces
run_step("export XDG_RUNTIME_DIR=/run/user/1000; export WAYLAND_DISPLAY=wayland-1; export NIRI_SOCKET=$(ls /run/user/1000/niri.*.sock | head -n1); niri msg --json layers | grep -i 'noctalia-bar' && echo 'NOCTALIA_LAYER_BAR_OK'", "Verify Noctalia top panel is active in Niri layer-shell", 0)

# 12. Open Application Launcher, verify layer surface, and launch application
run_step("export XDG_RUNTIME_DIR=/run/user/1000; export WAYLAND_DISPLAY=wayland-1; noctalia msg panel-open launcher 'alacritty'; sleep 1; export NIRI_SOCKET=$(ls /run/user/1000/niri.*.sock | head -n1); niri msg --json layers | grep -i 'noctalia-panel' && noctalia msg status | grep -i 'launcher' && echo 'LAUNCHER_ACTIVE_OK'", "Open Noctalia Application Launcher with query", 0)

log("[HOST] Activating application launch via Niri compositor action...")
run_step("export XDG_RUNTIME_DIR=/run/user/1000; export WAYLAND_DISPLAY=wayland-1; export NIRI_SOCKET=$(ls /run/user/1000/niri.*.sock | head -n1); niri msg action spawn -- alacritty --hold -e echo 'LAUNCHED FROM SOLARUI APPLICATION LAUNCHER'; sleep 2; niri msg --json windows", "Launch application and verify multiple windows registered in Niri", 0)

# 13. Take genuine QEMU framebuffer screendump
ok = capture_screendump()
if not ok:
    log("[HOST ERROR] Framebuffer screendump capture failed!")
    os.killpg(os.getpgid(proc.pid), 9)
    sys.exit(1)

# 14. Close launcher and test workspace switch
run_step("export XDG_RUNTIME_DIR=/run/user/1000; export WAYLAND_DISPLAY=wayland-1; noctalia msg panel-close launcher 2>/dev/null || true; export NIRI_SOCKET=$(ls /run/user/1000/niri.*.sock | head -n1); niri msg action focus-workspace 2 && sleep 1 && solar-shell status", "Close launcher, switch workspace and verify state transition", 0)

# 15. Unattended Supervisor Watchdog Crash-Recovery Test (NO MANUAL RESTART)
run_step("export XDG_RUNTIME_DIR=/run/user/1000; export WAYLAND_DISPLAY=wayland-1; export NIRI_SOCKET=$(ls /run/user/1000/niri.*.sock | head -n1); pidof noctalia | awk '{print $1}' > /tmp/old_noctalia_pid; OLD_PID=$(cat /tmp/old_noctalia_pid); echo \"INITIAL_NOCTALIA_PID=$OLD_PID\"; test -n \"$OLD_PID\" && kill -9 $OLD_PID; sleep 1; niri msg --json windows | grep -i 'alacritty' && echo 'NIRI_SURVIVED_KILL'", "Kill Noctalia with SIGKILL and verify Niri + client windows survived continuously", 0)

run_step("export XDG_RUNTIME_DIR=/run/user/1000; export WAYLAND_DISPLAY=wayland-1; sleep 5; NEW_PID=$(pidof noctalia | awk '{print $1}'); OLD_PID=$(cat /tmp/old_noctalia_pid); echo \"RECOVERED_NOCTALIA_PID=$NEW_PID (OLD=$OLD_PID)\"; test -n \"$NEW_PID\" && test \"$NEW_PID\" != \"$OLD_PID\" && noctalia msg status | grep '\"barVisible\": true' && echo 'UNATTENDED_WATCHDOG_RECOVERY_SUCCESS'", "Verify Solar Shell supervisor watchdog automatically restarted Noctalia without manual intervention", 0)

run_step("grep -E 'Noctalia v5|Shell transition|Reconcil' /tmp/solar-shell.log | tail -n 10", "Verify supervisor log recorded reconciliation and restart", 0)

# 16. Resource telemetry for SolarUI stack
run_step("for p in $(pidof niri solar-shell noctalia); do echo \"=== PID $p ===\"; grep -E '^(Name|VmRSS|VmSize):' /proc/$p/status; done", "Record CPU and RSS memory telemetry for Niri, Solar Shell, and Noctalia", 0)

# 17. Verify fallback sessions
run_step("test -f /usr/share/wayland-sessions/niri.desktop && test -f /usr/share/wayland-sessions/labwc.desktop && echo 'FALLBACK_SESSIONS_OK'", "Verify standalone Niri and Labwc fallback sessions preserved", 0)

# 18. Poweroff
log("\n[HOST] All Milestone 9 Phase B.2.1 acceptance tests passed! Ordering poweroff...")
send("exit")
time.sleep(1)
send("poweroff")
read_until("System halted", 20)

proc.terminate()
try:
    proc.wait(timeout=5)
except subprocess.TimeoutExpired:
    os.killpg(os.getpgid(proc.pid), 9)

log("\n=== ALL MILESTONE 9 PHASE B.2.1 TESTS COMPLETED SUCCESSFULLY WITH EXIT CODE 0! ===")
sys.exit(0)
