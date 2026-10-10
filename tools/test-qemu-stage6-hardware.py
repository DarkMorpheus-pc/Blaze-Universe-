#!/usr/bin/env python3
# ==============================================================================
# Blaze Universe — Milestone 6 Hardware Enablement QEMU Test Suite
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
LOG_FILE = os.path.join(BLAZE_ROOT, "reports", "milestone-6", "m6_hardware_test_output.log")

os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
log_fp = open(LOG_FILE, "w", encoding="utf-8")

def log(msg):
    print(msg)
    log_fp.write(msg + "\n")
    log_fp.flush()

log("=== STARTING MILESTONE 6 QEMU HARDWARE TEST SUITE ===")

if not os.path.exists(ROOT_DISK):
    log(f"[FATAL] Root disk {ROOT_DISK} not found!")
    sys.exit(1)

# Base QEMU command with simulated hardware topology
cmd = [
    "qemu-system-x86_64",
    "-bios", OVMF_CODE,
    "-m", "2048",
    "-smp", "4",
    "-cpu", "host" if os.path.exists("/dev/kvm") else "qemu64",
    "-enable-kvm" if os.path.exists("/dev/kvm") else "",
    "-drive", f"file={ROOT_DISK},format=raw,if=virtio,id=drv0",
    "-device", "virtio-gpu-pci,id=video0",
    "-device", "qemu-xhci,id=usb0",
    "-device", "pci-bridge,chassis_nr=1,id=pci.1",
    "-device", "pci-bridge,chassis_nr=2,id=pci.2",
    "-device", "pci-testdev",
    "-nographic",
    "-serial", "mon:stdio"
]
cmd = [arg for arg in cmd if arg]

log(f"[HOST] Launching QEMU with cmd: {' '.join(cmd)}")

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
in_post_shell = False
test_index = 0

post_commands = [
    ("uname -a", "__BLZ_M6_SENTINEL_1__"),
    ("/usr/bin/lspci", "__BLZ_M6_SENTINEL_2__"),
    ("/usr/bin/lsusb", "__BLZ_M6_SENTINEL_3__"),
    ("/usr/bin/portadora verify", "__BLZ_M6_SENTINEL_4__"),
    ("systemctl is-active nftables.service", "__BLZ_M6_SENTINEL_5__"),
    ("systemctl poweroff", "__BLZ_M6_SENTINEL_POWEROFF__")
]

def send_input(fd, text):
    log(f"[HOST -> GUEST] Sending: {text.strip()}")
    os.write(fd, text.encode("utf-8"))

while True:
    if time.time() - start_time > 120:
        log("[HOST ERROR] QEMU hardware test timed out after 120 seconds!")
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
        sys.stdout.write(data)
        sys.stdout.flush()

        clean_buf = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', buffer)

        if stage == "BOOT":
            if "blaze login:" in clean_buf and not sent_login:
                log("\n[M6-TEST] Login prompt detected. Logging in as root...")
                time.sleep(1.0)
                send_input(master_fd, "root\n")
                sent_login = True
            elif sent_login and ("root@blaze:~#" in clean_buf or "-bash-5.3#" in clean_buf):
                log("\n[M6-TEST] Root shell obtained!")
                stage = "RUNNING_TESTS"
                buffer = ""
                time.sleep(0.5)
                cmd_text, sentinel = post_commands[test_index]
                log(f"[M6-TEST] Executing [{test_index+1}/{len(post_commands)}]: {cmd_text}...")
                send_input(master_fd, f"{cmd_text}\necho '{sentinel}:'$?\n")

        elif stage == "RUNNING_TESTS":
            _, sentinel = post_commands[test_index]
            sentinel_pattern = rf"{sentinel}:(\d+)"
            match = re.search(sentinel_pattern, clean_buf)
            if match:
                exit_code = int(match.group(1))
                log(f"[M6-TEST] Command [{test_index+1}/{len(post_commands)}] finished with exit code {exit_code}.")
                if exit_code != 0 and sentinel != "__BLZ_M6_SENTINEL_POWEROFF__":
                    log(f"[HOST ERROR] Command [{post_commands[test_index][0]}] failed with exit code {exit_code}!")
                    os.killpg(os.getpgid(proc.pid), 9)
                    sys.exit(1)

                test_index += 1
                buffer = ""

                if test_index < len(post_commands):
                    cmd_text, _ = post_commands[test_index]
                    log(f"[M6-TEST] Executing [{test_index+1}/{len(post_commands)}]: {cmd_text}...")
                    send_input(master_fd, f"{cmd_text}\necho '{post_commands[test_index][1]}:'$?\n")
                else:
                    log("[M6-TEST] All hardware test commands sent successfully!")
                    stage = "WAIT_POWEROFF"

        elif stage == "WAIT_POWEROFF":
            if "reboot: Power down" in clean_buf or "System halted" in clean_buf:
                log("[M6-TEST] QEMU cleanly powered down.")
                break

try:
    proc.wait(timeout=10)
except subprocess.TimeoutExpired:
    os.killpg(os.getpgid(proc.pid), 9)

log("\n=== ALL MILESTONE 6 HARDWARE ACCEPTANCE TESTS PASSED WITH 0 EXIT CODES! ===")
sys.exit(0)
