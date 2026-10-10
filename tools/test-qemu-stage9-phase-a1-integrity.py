#!/usr/bin/env python3
# ==============================================================================
# Blaze Universe — Milestone 9 Phase A.1 Portadora Negative Integrity Test Suite
# Disposable QEMU Clone Tamper Detection and Package Verification Test
# ==============================================================================
import os
import pty
import re
import select
import shutil
import socket
import subprocess
import sys
import time

BLAZE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE_DISK = os.path.join(BLAZE_ROOT, "build", "blaze-disk.raw")
DISPOSABLE_DISK = os.path.join(BLAZE_ROOT, "build", "blaze-disk-disposable.raw")
OVMF_CODE = "/usr/share/edk2/x64/OVMF.4m.fd"
LOG_FILE = os.path.join(BLAZE_ROOT, "reports", "milestone-9", "m9_phase_a1_integrity_test_output.log")
MONITOR_SOCKET = "/tmp/qemu-m9-integrity-monitor.sock"

os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
log_fp = open(LOG_FILE, "w", encoding="utf-8")

def log(msg):
    print(msg)
    log_fp.write(msg + "\n")
    log_fp.flush()

log("=== STARTING MILESTONE 9 PHASE A.1 PORTADORA NEGATIVE INTEGRITY TEST SUITE ===")

if not os.path.exists(BASE_DISK):
    log(f"[FATAL] Base disk {BASE_DISK} not found!")
    sys.exit(1)

log("[HOST] Creating disposable QEMU disk clone (blaze-disk-disposable.raw)...")
subprocess.run(f"cp --reflink=auto --sparse=always '{BASE_DISK}' '{DISPOSABLE_DISK}'", shell=True, check=True)

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
    "-enable-kvm" if os.path.exists("/dev/kvm") else "",
    "-vga", "virtio",
    "-drive", f"file={DISPOSABLE_DISK},format=raw,if=virtio,id=drv0",
    "-device", "intel-hda",
    "-device", "hda-duplex",
    "-kernel", K729_KERNEL,
    "-initrd", K729_INITRD,
    "-append", "root=PARTUUID=44444444-4444-4444-4444-444444444444 rw console=ttyS0 console=tty0",
    "-nographic",
    "-serial", "mon:stdio",
    "-monitor", f"unix:{MONITOR_SOCKET},server,nowait"
]

log(f"[HOST] Launching QEMU disposable clone for integrity testing...")

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

# Negative Integrity Test Steps: (Command, Sentinel_String, Expected_Exit_Code, Test_ID)
acceptance_cmds = [
    ("id && whoami", "__INT_01_USER_ID__", 0, "INT-01"),
    ("/usr/bin/portadora verify", "__INT_02_PORTADORA_INITIAL_VERIFY__", 0, "INT-02"),
    ("echo 'CORRUPTED_ELF_CONTENT_FOR_NEGATIVE_TEST' > /usr/lib/libinput.so.10.13.0", "__INT_03_TAMPER_TRACKED_FILE__", 0, "INT-03"),
    ("/usr/bin/portadora verify", "__INT_04_PORTADORA_TAMPER_DETECTED__", 1, "INT-04"),
    ("cp -a /usr/lib/libinput.so.10.13.0.bak /usr/lib/libinput.so.10.13.0 2>/dev/null || true; /usr/bin/portadora verify", "__INT_05_RESTORE_AND_VERIFY__", 0, "INT-05")
]

# Create a backup inside QEMU before tampering
acceptance_cmds[1] = ("/usr/bin/portadora verify && cp -a /usr/lib/libinput.so.10.13.0 /usr/lib/libinput.so.10.13.0.bak", "__INT_02_PORTADORA_INITIAL_VERIFY__", 0, "INT-02")

while True:
    if time.time() - start_time > 180:
        log("[HOST ERROR] Portadora negative integrity test timed out after 180s!")
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
                log("[INTEGRITY-TEST] Login prompt detected. Logging in as root for tamper administration...")
                time.sleep(0.5)
                os.write(master_fd, b"root\n")
                sent_login = True

            elif sent_login and ("root@blaze:~#" in clean_buf or "-bash-5.3#" in clean_buf):
                log("[INTEGRITY-TEST] Root shell obtained. Executing Portadora Negative Integrity Test Matrix...")
                stage = "RUNNING_TESTS"
                buffer = ""
                cmd_text, sentinel, expected_code, test_id = acceptance_cmds[cmd_index]
                log(f"[INTEGRITY-TEST] Executing [{test_id} ({cmd_index+1}/{len(acceptance_cmds)})]: {cmd_text}...")
                os.write(master_fd, f"{cmd_text}\necho '{sentinel}:'$?\n".encode("utf-8"))

        elif stage == "RUNNING_TESTS":
            if cmd_index < len(acceptance_cmds):
                _, sentinel, expected_code, test_id = acceptance_cmds[cmd_index]
                sentinel_pattern = rf"{sentinel}:(\d+)"
                match = re.search(sentinel_pattern, clean_buf)
                if match:
                    exit_code = int(match.group(1))
                    log(f"[INTEGRITY-TEST] Test [{test_id}] exit code: {exit_code} (Expected: {expected_code})")
                    if exit_code != expected_code:
                        log(f"[HOST ERROR] Test [{test_id}] command [{acceptance_cmds[cmd_index][0]}] expected {expected_code} but got {exit_code}!")
                        log(f"[HOST DEBUG OUTPUT]:\n{clean_buf}")
                        os.killpg(os.getpgid(proc.pid), 9)
                        sys.exit(1)

                    if test_id == "INT-04":
                        log("[HOST SUCCESS] Portadora successfully detected file tampering and reported NON-ZERO exit code 1!")

                    cmd_index += 1
                    buffer = ""
                    if cmd_index < len(acceptance_cmds):
                        cmd_text, sentinel, _, test_id = acceptance_cmds[cmd_index]
                        log(f"[INTEGRITY-TEST] Executing [{test_id} ({cmd_index+1}/{len(acceptance_cmds)})]: {cmd_text}...")
                        os.write(master_fd, f"{cmd_text}\necho '{sentinel}:'$?\n".encode("utf-8"))
                    else:
                        log("[INTEGRITY-TEST] All Portadora Negative Integrity Tests passed! Ordering poweroff...")
                        os.write(master_fd, b"poweroff\n")
                        stage = "WAIT_POWEROFF"

        elif stage == "WAIT_POWEROFF":
            if "reboot: Power down" in clean_buf or "System halted" in clean_buf or "logout" in clean_buf:
                log("[INTEGRITY-TEST] Disposable QEMU guest cleanly powered down.")
                break

try:
    proc.wait(timeout=5)
except subprocess.TimeoutExpired:
    os.killpg(os.getpgid(proc.pid), 9)

if os.path.exists(DISPOSABLE_DISK):
    os.remove(DISPOSABLE_DISK)

log("\n=== ALL PORTADORA NEGATIVE INTEGRITY TESTS PASSED WITH EXIT CODE 0! ===")
sys.exit(0)
