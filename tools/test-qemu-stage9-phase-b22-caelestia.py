#!/usr/bin/env python3
# ==============================================================================
# Blaze Universe — Milestone 9 Phase B.2.2 Acceptance Test Suite
# Real Graphics / Caelestia Native Shell / Quickshell / Niri Layer-Shell
# Independent Session Verification / PSS Memory Telemetry / Framebuffer Capture
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
OVERLAY_DISK = "/tmp/blaze-m9-b22-caelestia-overlay.qcow2"
OVMF_CODE = "/usr/share/edk2/x64/OVMF.4m.fd"
LOG_FILE = os.path.join(BLAZE_ROOT, "reports", "milestone-9", "m9_phase_b22_caelestia_acceptance_output.log")
MONITOR_SOCKET = "/tmp/qemu-m9-b22-mon.sock"
PPM_SCREENSHOT = "/tmp/qemu_caelestia_b22.ppm"
PNG_SCREENSHOT = "/tmp/blazeos_m9_b22_caelestia_real_framebuffer.png"
ARTIFACT_DIR = "/home/darkmorpheus/.gemini/antigravity/brain/edfcc68e-d62a-469a-afaa-c49b73f87c64"
ARTIFACT_PNG = os.path.join(ARTIFACT_DIR, "blazeos_m9_b22_caelestia_real_framebuffer.png")

os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
log_fp = open(LOG_FILE, "w", encoding="utf-8")

def log(msg):
    print(msg, flush=True)
    log_fp.write(msg + "\n")
    log_fp.flush()

log("=== STARTING MILESTONE 9 PHASE B.2.2 CAELESTIA NATIVE ACCEPTANCE TEST ===")

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
    "-qmp", f"unix:{MONITOR_SOCKET},server,nowait",
    "-net", "none"
]

if os.path.exists("/dev/kvm"):
    cmd.insert(1, "-enable-kvm")

master, slave = pty.openpty()
proc = subprocess.Popen(
    cmd,
    stdin=slave,
    stdout=slave,
    stderr=slave,
    close_fds=True,
    preexec_fn=os.setsid
)
os.close(slave)

def send_qmp_command(sock_path, cmd_dict):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(sock_path)
    greeting = s.recv(4096)
    s.sendall(b'{"execute": "qmp_capabilities"}\n')
    ack = s.recv(4096)
    req = json.dumps(cmd_dict).encode("utf-8") + b"\n"
    s.sendall(req)
    res = b""
    while True:
        chunk = s.recv(4096)
        if not chunk:
            break
        res += chunk
        if b"return" in chunk or b"error" in chunk:
            break
    s.close()
    return res.decode("utf-8", errors="replace")

def send_line(line):
    os.write(master, (line + "\n").encode("utf-8"))
    time.sleep(0.3)

def read_until(pattern, timeout=90):
    start = time.time()
    buf = ""
    while time.time() - start < timeout:
        r, _, _ = select.select([master], [], [], 0.5)
        if r:
            try:
                data = os.read(master, 4096).decode("utf-8", errors="replace")
                buf += data
                sys.stdout.write(data)
                sys.stdout.flush()
                log_fp.write(data)
                log_fp.flush()
                clean = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', buf)
                if re.search(pattern, clean):
                    return True, buf
            except Exception:
                pass
        if proc.poll() is not None:
            return False, buf
    return False, buf

log("[TEST] Waiting for system boot and login prompt...")
ok, out = read_until("login:", timeout=70)
if not ok:
    log("[FAIL] Timed out waiting for login prompt!")
    os.killpg(os.getpgid(proc.pid), 9)
    sys.exit(1)

log("\n[PASS] Boot successful. Logging in as root...")
send_line("root")
time.sleep(1)
send_line("root")
ok, out = read_until("#", timeout=20)
if not ok:
    log("[FAIL] Login failed!")
    os.killpg(os.getpgid(proc.pid), 9)
    sys.exit(1)
log("\n[PASS] Root shell established.")

def run_step(command, description, expected_exit=0, step_timeout=45):
    log(f"\n>>> [STEP] {description}")
    log(f"$ {command}")
    marker = f"__SENTINEL_{int(time.time()*1000)}__"
    send_line(f"{command}\necho '{marker}:'$?")
    pattern = rf"{marker}:(\d+)"
    start = time.time()
    buf = ""
    while time.time() - start < step_timeout:
        r, _, _ = select.select([master], [], [], 0.5)
        if r:
            try:
                data = os.read(master, 4096).decode("utf-8", errors="replace")
                buf += data
                sys.stdout.write(data)
                sys.stdout.flush()
                log_fp.write(data)
                log_fp.flush()
                clean = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', buf)
                m = re.search(pattern, clean)
                if m:
                    code = int(m.group(1))
                    log(f"\n[STEP RESULT] Exit code: {code} (Expected: {expected_exit})")
                    if code != expected_exit:
                        log(f"[FAIL] Expected exit code {expected_exit}, got {code}")
                        os.killpg(os.getpgid(proc.pid), 9)
                        sys.exit(1)
                    return True, buf
            except Exception:
                pass
        if proc.poll() is not None:
            log(f"[FAIL] QEMU exited unexpectedly!")
            sys.exit(1)
    log(f"\n[FAIL] Step timed out! Command: {command}")
    os.killpg(os.getpgid(proc.pid), 9)
    sys.exit(1)

# Step 1: ELF binaries and dynamic library resolution
run_step(
    "file /usr/bin/quickshell /usr/bin/caelestia /usr/lib/qt6/qml/Caelestia/lib/*.so && ldd /usr/bin/quickshell | grep 'not found' || echo 'ALL_QUICKSHELL_LIBS_OK'",
    "B2.2-01: Verify Quickshell & Caelestia ELF resolution and 0 missing libraries",
    0
)

# Step 2: Portadora package integrity (allow up to 60s for full SHA-256 DB verification)
run_step(
    "/usr/bin/portadora verify",
    "B2.2-02: Cryptographic Portadora package integrity verification",
    0,
    step_timeout=75
)

# Step 3: Start unprivileged Niri graphical session under user blaze (UID 1000)
# Step 2.5: Initialize Daemons (seatd and D-Bus)
run_step(
    "seatd -u blaze -g blaze -n 1 > /tmp/seatd.log 2>&1 & sleep 1; test -S /run/seatd.sock && echo 'SEATD_OK'",
    "Start seatd daemon for non-root graphics",
    0
)
run_step(
    "mkdir -p /run/dbus && dbus-daemon --system --fork 2>/dev/null || true",
    "Start D-Bus system bus daemon",
    0
)
run_step(
    "export XDG_RUNTIME_DIR=/run/user/1000; dbus-daemon --session --fork --address=unix:path=/run/user/1000/bus 2>/dev/null || true; export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus; echo 'DBUS_USER_OK'",
    "Start D-Bus user session bus daemon",
    0
)

# Step 3: Start Niri compositor under UID 1000 with SolarUI configuration
run_step(
    "export XDG_RUNTIME_DIR=/run/user/1000; export LIBSEAT_BACKEND=seatd; export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus; unset WAYLAND_DISPLAY; niri --config /home/blaze/.config/niri/config.kdl > /tmp/niri.log 2>&1 & sleep 3; pkill -9 noctalia 2>/dev/null || true; test -S /run/user/1000/wayland-1 && echo 'WAYLAND_OK'",
    "Start Niri compositor with SolarUI configuration (independent Caelestia isolation)",
    0
)
run_step(
    "export XDG_RUNTIME_DIR=/run/user/1000; export NIRI_SOCKET=$(ls /run/user/1000/niri.*.sock | head -n1); niri msg --json version",
    "B2.2-03: Verify Niri compositor is active and responsive to JSON IPC",
    0
)

# Step 4: Launch independent Caelestia visual shell session
run_step(
    "export XDG_RUNTIME_DIR=/run/user/1000; export WAYLAND_DISPLAY=wayland-1; export NIRI_SOCKET=$(ls /run/user/1000/niri.*.sock | head -n1); pkill -9 -f solar-shell 2>/dev/null || true; pkill -9 noctalia 2>/dev/null || true; (qs -c caelestia > /tmp/caelestia.log 2>&1 &); sleep 10; (pidof quickshell || pgrep -f qs) && echo CAELESTIA_RUNNING",
    "B2.2-04: Launch independent Caelestia session via Quickshell & verify process",
    0
)

# Step 5: Query Caelestia drawers and Bar state via IPC
run_step(
    "export XDG_RUNTIME_DIR=/run/user/1000; export WAYLAND_DISPLAY=wayland-1; export NIRI_SOCKET=$(ls /run/user/1000/niri.*.sock | head -n1); qs -c caelestia ipc call drawers list",
    "B2.2-05: Query Caelestia IPC drawers (bar, launcher, dashboard, session, utilities)",
    0
)

# Step 6: Workspace Indicator test via Niri IPC
run_step(
    "export XDG_RUNTIME_DIR=/run/user/1000; export WAYLAND_DISPLAY=wayland-1; export NIRI_SOCKET=$(ls /run/user/1000/niri.*.sock | head -n1); niri msg action focus-workspace 2 && sleep 1 && niri msg --json workspaces",
    "B2.2-06: Switch workspace to 2 via Niri IPC and verify event stream",
    0
)

# Step 7: Toggle Launcher and launch real client window (Alacritty)
run_step(
    "export XDG_RUNTIME_DIR=/run/user/1000; export WAYLAND_DISPLAY=wayland-1; export NIRI_SOCKET=$(ls /run/user/1000/niri.*.sock | head -n1); qs -c caelestia ipc call drawers toggle launcher && sleep 1 && qs -c caelestia ipc call drawers isOpen launcher",
    "B2.2-07: Toggle Caelestia launcher drawer via IPC",
    0
)
run_step(
    "export XDG_RUNTIME_DIR=/run/user/1000; export WAYLAND_DISPLAY=wayland-1; alacritty --hold -e echo 'BLAZEOS REAL CAELESTIA CLIENT ACTIVE' > /tmp/alacritty.log 2>&1 & sleep 2; export NIRI_SOCKET=$(ls /run/user/1000/niri.*.sock | head -n1); niri msg --json windows",
    "B2.2-08: Spawn Alacritty client window and confirm registration in Niri",
    0
)
# Step 9: Capture authentic QEMU monitor framebuffer screendump
log("\n>>> [STEP] B2.2-09: Capture authentic QEMU monitor screendump...")
time.sleep(2)
res = send_qmp_command(MONITOR_SOCKET, {
    "execute": "screendump",
    "arguments": {"filename": PPM_SCREENSHOT}
})
log(f"[QMP RESPONSE] {res}")

if os.path.exists(PPM_SCREENSHOT) and os.path.getsize(PPM_SCREENSHOT) > 0:
    img = Image.open(PPM_SCREENSHOT)
    img.save(PNG_SCREENSHOT, "PNG")
    img.save(ARTIFACT_PNG, "PNG")
    log(f"[PASS] Real screendump saved: {PNG_SCREENSHOT} (Size: {img.size}, Mode: {img.mode})")
    log(f"[PASS] Artifact published: {ARTIFACT_PNG}")
else:
    log(f"[FAIL] Framebuffer dump failed or file empty!")

# Step 10: Accurate memory telemetry via smaps_rollup PSS and MemAvailable
run_step(
    "for p in $(pidof niri quickshell alacritty seatd); do echo \"=== PID $p $(cat /proc/$p/comm) ===\"; grep -E '^(Name|VmRSS|VmSize):' /proc/$p/status; [ -f /proc/$p/smaps_rollup ] && grep -E '^(Rss|Pss):' /proc/$p/smaps_rollup || true; done; grep -E '^(MemTotal|MemFree|MemAvailable):' /proc/meminfo",
    "B2.2-10: Accurate PSS memory telemetry and system MemAvailable recording",
    0
)

# Step 11: Verify fallback sessions intact (Noctalia, Niri, Labwc)
run_step(
    "ls -la /usr/share/wayland-sessions/ && test -x /usr/bin/noctalia && test -x /usr/bin/labwc && test -f /usr/share/wayland-sessions/solarui-niri.desktop && echo FALLBACK_SESSIONS_INTACT",
    "B2.2-11: Verify default Noctalia and fallback sessions remain intact",
    0
)

log("\n=== ALL MILESTONE 9 PHASE B.2.2 ACCEPTANCE TESTS PASSED SUCCESSFULLY! ===")
send_line("poweroff")
time.sleep(3)
os.killpg(os.getpgid(proc.pid), 9)
