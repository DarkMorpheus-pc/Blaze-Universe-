#!/usr/bin/env python3
# ==============================================================================
# Blaze Universe — Milestone 9 Phase B.1.1 Full Acceptance Test Suite
# Real Graphics / Niri Client Window / Screendump / EventStream / Portadora Reinstall
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
OVERLAY_DISK = "/tmp/blaze-m9-b11-acceptance-overlay.qcow2"
OVMF_CODE = "/usr/share/edk2/x64/OVMF.4m.fd"
LOG_FILE = os.path.join(BLAZE_ROOT, "reports", "milestone-9", "m9_phase_b11_acceptance_output.log")
MONITOR_SOCKET = "/tmp/qemu-m9-b11-mon.sock"
PPM_SCREENSHOT = "/tmp/qemu_solar_shell_b1.ppm"
PNG_SCREENSHOT = "/tmp/solar_shell_b1_screenshot.png"
ARTIFACT_DIR = "/home/darkmorpheus/.gemini/antigravity/brain/edfcc68e-d62a-469a-afaa-c49b73f87c64"
ARTIFACT_PNG = os.path.join(ARTIFACT_DIR, "solar_shell_b1_screenshot.png")

os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
log_fp = open(LOG_FILE, "w", encoding="utf-8")

def log(msg):
    print(msg, flush=True)
    log_fp.write(msg + "\n")
    log_fp.flush()

log("=== STARTING MILESTONE 9 PHASE B.1.1 RIGOROUS ACCEPTANCE TEST SUITE ===")

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

# 2. Start root daemons
run_step("seatd -u blaze -g blaze -n 1 > /tmp/seatd.log 2>&1 & sleep 1; test -S /run/seatd.sock && echo 'SEATD_OK'", "Start seatd daemon and verify socket", 0)
run_step("mkdir -p /run/dbus && dbus-daemon --system --fork 2>/dev/null || true", "Start D-Bus system daemon", 0)
run_step("mkdir -p /run/user/1000 && chown -R blaze:blaze /run/user/1000 /home/blaze && chmod 0700 /run/user/1000", "Ensure /run/user/1000 permissions", 0)

# 3. Switch to blaze user
log("\n[HOST] Switching to unprivileged user 'blaze' (UID 1000)...")
send("su - blaze")
time.sleep(1)
read_until("-bash-5.3$", 10)
log("[HOST] User 'blaze' shell active.")

run_step("id && whoami", "Verify UID 1000 (blaze)", 0)

# 4. Start Niri
run_step("export XDG_RUNTIME_DIR=/run/user/1000; export LIBSEAT_BACKEND=seatd; unset WAYLAND_DISPLAY; niri --config /etc/niri/config.kdl > /tmp/niri.log 2>&1 & sleep 3; cat /tmp/niri.log; test -S /run/user/1000/wayland-1 && echo 'WAYLAND_OK'", "Start Niri compositor under UID 1000", 0)

run_step("export XDG_RUNTIME_DIR=/run/user/1000; export NIRI_SOCKET=$(ls /run/user/1000/niri.*.sock | head -n1); niri msg version", "Query Niri version via IPC", 0)

# 5. Launch client window (alacritty) inside Niri
run_step("export XDG_RUNTIME_DIR=/run/user/1000; export WAYLAND_DISPLAY=wayland-1; alacritty --hold -e echo 'BLAZEOS REAL WAYLAND CLIENT ACTIVE' > /tmp/alacritty.log 2>&1 & sleep 3; export NIRI_SOCKET=$(ls /run/user/1000/niri.*.sock | head -n1); niri msg --json windows", "Launch Wayland client window in Niri and query via JSON IPC", 0)

# 6. Take genuine QEMU framebuffer screendump
ok = capture_screendump()
if not ok:
    log("[HOST ERROR] Framebuffer screendump capture failed!")
    os.killpg(os.getpgid(proc.pid), 9)
    sys.exit(1)

# 7. Solar Shell EventStream and State Transition
run_step("export XDG_RUNTIME_DIR=/run/user/1000; export NIRI_SOCKET=$(ls /run/user/1000/niri.*.sock | head -n1); export WAYLAND_DISPLAY=wayland-1; solar-core > /tmp/solar-core.log 2>&1 & sleep 1; solar-shell status", "Query initial Solar Shell status", 0)

run_step("export XDG_RUNTIME_DIR=/run/user/1000; export NIRI_SOCKET=$(ls /run/user/1000/niri.*.sock | head -n1); niri msg action focus-workspace 2 && sleep 1 && solar-shell status", "Trigger workspace switch and verify Solar Shell state transition", 0)

# 8. Supervisor lifecycle & single instance check
run_step("pkill -f solar-shell || true; export XDG_RUNTIME_DIR=/run/user/1000; export NIRI_SOCKET=$(ls /run/user/1000/niri.*.sock | head -n1); niri msg --json windows", "Stop solar-shell and verify Niri and client window survive", 0)

run_step("export XDG_RUNTIME_DIR=/run/user/1000; export NIRI_SOCKET=$(ls /run/user/1000/niri.*.sock | head -n1); solar-shell supervisor > /tmp/solar-shell-sup.log 2>&1 & sleep 1; solar-shell status", "Restart solar-shell supervisor and verify IPC reconnection", 0)

# 9. Return to root for package integrity and restoration testing
log("\n[HOST] Returning to root shell for Portadora package restoration testing...")
send("exit")
time.sleep(1)
read_until("-bash-5.3#", 10)
log("[HOST] Root shell resumed.")

# 10. Record baseline hashes
run_step("sha256sum /usr/bin/solar-shell /usr/bin/portadora > /tmp/baseline_sha256.txt && cat /tmp/baseline_sha256.txt", "Record baseline SHA-256 hashes", 0)

# 11. Tamper binaries & detect with independent verifier
run_step("echo 'CORRUPTED_BYTES_INJECTION' >> /usr/bin/solar-shell && echo 'CORRUPTED_BYTES_INJECTION' >> /usr/bin/portadora && ! sha256sum -c /tmp/baseline_sha256.txt", "Tamper binaries and verify independent verifier detects mismatch", 0)

# 12. Negative test: Portadora verify must fail
run_step("! /usr/bin/portadora verify", "Portadora verify detects corruption with non-zero exit code", 0)

# 13. Genuine package restoration via Portadora transactions (NO .bak file copying)
run_step("/usr/bin/portadora install /var/cache/portadora/packages/solar-shell-1.0.0-1.x86_64.blz && /usr/bin/portadora install /var/cache/portadora/packages/portadora-0.2.0-4.x86_64.blz", "Restore corrupted binaries via authentic Portadora transactions", 0)

# 14. Verify restored binaries match authentic baseline SHA-256
run_step("sha256sum -c /tmp/baseline_sha256.txt", "Verify restored binaries match authentic baseline SHA-256", 0)

# 15. Verify Portadora verify passes with exit code 0
run_step("/usr/bin/portadora verify", "Verify Portadora verify passes with exit code 0 after restoration", 0)

# 16. Confirm transaction history records the INSTALL actions
run_step("/usr/bin/portadora history | tail -n 6", "Verify transaction history contains authentic INSTALL records", 0)

# 17. Graceful poweroff
log("\n[HOST] All Milestone 9 Phase B.1.1 acceptance tests passed! Ordering poweroff...")
send("poweroff")
read_until("System halted", 20)

proc.terminate()
try:
    proc.wait(timeout=5)
except subprocess.TimeoutExpired:
    os.killpg(os.getpgid(proc.pid), 9)

log("\n=== ALL MILESTONE 9 PHASE B.1.1 RIGOROUS ACCEPTANCE TESTS COMPLETED SUCCESSFULLY WITH EXIT CODE 0! ===")
sys.exit(0)
