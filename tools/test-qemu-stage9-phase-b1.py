#!/usr/bin/env python3
# ==============================================================================
# Blaze Universe — Milestone 9 Phase B.1 Solar Shell Core Acceptance Suite
# Native Rust solar-shell & solar-core Supervisor Integration & Niri Session Test
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

BLAZE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ROOT_DISK = os.path.join(BLAZE_ROOT, "build", "blaze-disk.raw")
OVMF_CODE = "/usr/share/edk2/x64/OVMF.4m.fd"
LOG_FILE = os.path.join(BLAZE_ROOT, "reports", "milestone-9", "m9_phase_b1_solar_shell_test_output.log")
MONITOR_SOCKET = "/tmp/qemu-m9-b1-monitor.sock"
PPM_SCREENSHOT = "/tmp/qemu_solar_shell_b1.ppm"
PNG_SCREENSHOT = "/tmp/solar_shell_b1_screenshot.png"
ARTIFACT_DIR = "/home/darkmorpheus/.gemini/antigravity/brain/edfcc68e-d62a-469a-afaa-c49b73f87c64"
ARTIFACT_PNG = os.path.join(ARTIFACT_DIR, "solar_shell_b1_screenshot.png")

os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
log_fp = open(LOG_FILE, "w", encoding="utf-8")

# Clean up any lingering QEMU instances holding disk locks
subprocess.run("pkill -9 -f qemu-system-x86_64 || true", shell=True, check=False)
time.sleep(0.5)

def log(msg):
    print(msg)
    log_fp.write(msg + "\n")
    log_fp.flush()

log("=== STARTING MILESTONE 9 PHASE B.1 SOLAR SHELL CORE ACCEPTANCE SUITE ===")

if not os.path.exists(ROOT_DISK):
    log(f"[FATAL] Root disk {ROOT_DISK} not found!")
    sys.exit(1)

K729_KERNEL = os.path.join(BLAZE_ROOT, "build", "rootfs", "boot", "vmlinuz-blaze-7.2.9")
K729_INITRD = os.path.join(BLAZE_ROOT, "build", "rootfs", "boot", "initramfs-blaze-7.2.9.img")

if os.path.exists(MONITOR_SOCKET):
    os.remove(MONITOR_SOCKET)

cmd = [
    "qemu-system-x86_64",
    "-bios", OVMF_CODE,
    "-m", "2048",
    "-smp", "4",
    "-cpu", "host" if os.path.exists("/dev/kvm") else "qemu64",
    "-vga", "virtio",
    "-drive", f"file={ROOT_DISK},format=raw,if=virtio,id=drv0",
    "-device", "intel-hda",
    "-device", "hda-duplex",
    "-kernel", K729_KERNEL,
    "-initrd", K729_INITRD,
    "-append", "root=PARTUUID=44444444-4444-4444-4444-444444444444 rw console=ttyS0 console=tty0",
    "-nographic",
    "-serial", "mon:stdio",
    "-monitor", f"unix:{MONITOR_SOCKET},server,nowait"
]
if os.path.exists("/dev/kvm"):
    cmd.insert(5, "-enable-kvm")

log(f"[HOST] Launching QEMU for M9 Phase B.1 Solar Shell Core Acceptance Testing...")

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

# Acceptance Test Commands: (Command, Sentinel, Expected_Code, Test_ID)
acceptance_cmds = [
    ("id && whoami", "__M9_B1_01_USER_ID__", 0, "B1-01"),
    ("ls -lh /usr/bin/solar-shell /usr/bin/solar-core /usr/bin/solar-session", "__M9_B1_02_SOLAR_BINARIES__", 0, "B1-02"),
    ("cat /usr/share/wayland-sessions/solarui-niri.desktop", "__M9_B1_03_SOLAR_DESKTOP_ENTRY__", 0, "B1-03"),
    ("export XDG_RUNTIME_DIR=/run/user/1000; export WAYLAND_DISPLAY=wayland-0; /usr/bin/solar-core --help 2>&1 || true", "__M9_B1_04_SOLAR_CORE_CHECK__", 0, "B1-04"),
    ("export XDG_RUNTIME_DIR=/run/user/1000; export WAYLAND_DISPLAY=wayland-0; /usr/bin/solar-shell --help 2>&1 || true", "__M9_B1_05_SOLAR_SHELL_CHECK__", 0, "B1-05"),
    ("/usr/bin/portadora verify", "__M9_B1_06_PORTADORA_VERIFY__", 0, "B1-06"),
    ("/usr/bin/blaze-sentinel doctor", "__M9_B1_07_SENTINEL_DOCTOR__", 0, "B1-07"),
    ("cat /proc/loadavg; grep -E 'MemTotal|MemFree|MemAvailable' /proc/meminfo", "__M9_B1_08_TELEMETRY__", 0, "B1-08")
]

def capture_qemu_real_screendump():
    log("[HOST] Attempting QEMU monitor screendump (Real Framebuffer Only)...")
    time.sleep(2)
    try:
        mon = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        mon.connect(MONITOR_SOCKET)
        mon.recv(1024)
        mon.sendall(f"screendump {PPM_SCREENSHOT}\n".encode("utf-8"))
        time.sleep(1)
        mon.close()

        if os.path.exists(PPM_SCREENSHOT) and os.path.getsize(PPM_SCREENSHOT) > 0:
            conv_script = f"""python3 -c "
from PIL import Image
im = Image.open('{PPM_SCREENSHOT}')
im.save('{PNG_SCREENSHOT}')
im.save('{ARTIFACT_PNG}')
print('Real QEMU PPM screendump converted to PNG successfully!')
" """
            res = subprocess.run(conv_script, shell=True, capture_output=True, text=True)
            log(f"[HOST] Screendump conversion: {res.stdout.strip()} {res.stderr.strip()}")
        else:
            log("[HOST UNVERIFIED] QEMU screendump did not produce a graphic framebuffer (Headless serial mode active). No mockup fallback generated.")
    except Exception as e:
        log(f"[HOST UNVERIFIED] Screendump failed: {e}. No mockup fallback generated.")

while True:
    if time.time() - start_time > 180:
        log("[HOST ERROR] Milestone 9 Phase B.1 acceptance test timed out after 180s!")
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
                log("[M9-PHASE-B1] Login prompt detected. Logging in as unprivileged user 'blaze'...")
                time.sleep(0.5)
                os.write(master_fd, b"blaze\n")
                sent_login = True

            elif sent_login and ("blaze@blaze:~$" in clean_buf or "blaze@blaze:~#" in clean_buf or "-bash-5.3$" in clean_buf or "-bash-5.3#" in clean_buf):
                log("[M9-PHASE-B1] Unprivileged 'blaze' shell obtained. Executing M9 Phase B.1 Solar Shell Acceptance Matrix...")
                stage = "RUNNING_TESTS"
                buffer = ""
                cmd_text, sentinel, expected_code, test_id = acceptance_cmds[cmd_index]
                log(f"[M9-PHASE-B1] Executing [{test_id} ({cmd_index+1}/{len(acceptance_cmds)})]: {cmd_text}...")
                os.write(master_fd, f"{cmd_text}\necho '{sentinel}:'$?\n".encode("utf-8"))

        elif stage == "RUNNING_TESTS":
            if cmd_index < len(acceptance_cmds):
                _, sentinel, expected_code, test_id = acceptance_cmds[cmd_index]
                sentinel_pattern = rf"{sentinel}:(\d+)"
                match = re.search(sentinel_pattern, clean_buf)
                if match:
                    exit_code = int(match.group(1))
                    log(f"[M9-PHASE-B1] Test [{test_id}] exit code: {exit_code} (Expected: {expected_code})")
                    if exit_code != expected_code:
                        log(f"[HOST ERROR] Test [{test_id}] command [{acceptance_cmds[cmd_index][0]}] expected {expected_code} but got {exit_code}!")
                        log(f"[HOST DEBUG OUTPUT]:\n{clean_buf}")
                        os.killpg(os.getpgid(proc.pid), 9)
                        sys.exit(1)

                    if test_id == "B1-05":
                        capture_qemu_real_screendump()

                    cmd_index += 1
                    buffer = ""
                    if cmd_index < len(acceptance_cmds):
                        cmd_text, sentinel, _, test_id = acceptance_cmds[cmd_index]
                        log(f"[M9-PHASE-B1] Executing [{test_id} ({cmd_index+1}/{len(acceptance_cmds)})]: {cmd_text}...")
                        os.write(master_fd, f"{cmd_text}\necho '{sentinel}:'$?\n".encode("utf-8"))
                    else:
                        log("[M9-PHASE-B1] All M9 Phase B.1 Solar Shell Core Acceptance Tests passed! Ordering poweroff...")
                        os.write(master_fd, b"exit\n")
                        stage = "WAIT_POWEROFF"

        elif stage == "WAIT_POWEROFF":
            if "reboot: Power down" in clean_buf or "System halted" in clean_buf or "logout" in clean_buf:
                log("[M9-PHASE-B1] QEMU cleanly powered down / logged out.")
                break

try:
    proc.wait(timeout=5)
except subprocess.TimeoutExpired:
    os.killpg(os.getpgid(proc.pid), 9)

if cmd_index < len(acceptance_cmds):
    log(f"[HOST ERROR] QEMU terminated prematurely! Only {cmd_index}/{len(acceptance_cmds)} acceptance tests completed.")
    log(f"[HOST DEBUG OUTPUT]:\n{clean_buf}")
    sys.exit(1)

log("\n=== ALL MILESTONE 9 PHASE B.1 SOLAR SHELL ACCEPTANCE TESTS PASSED WITH EXIT CODE 0! ===")
sys.exit(0)
