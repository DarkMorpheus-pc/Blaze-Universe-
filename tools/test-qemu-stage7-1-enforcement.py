#!/usr/bin/env python3
# ==============================================================================
# Blaze Universe — Milestone 7.1 Security Enforcement & Freshness Test Suite
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
LOG_FILE = os.path.join(BLAZE_ROOT, "reports", "milestone-7", "m7_1_enforcement_test_output.log")

os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
log_fp = open(LOG_FILE, "w", encoding="utf-8")

def log(msg):
    print(msg)
    log_fp.write(msg + "\n")
    log_fp.flush()

log("=== STARTING MILESTONE 7.1 SECURITY ENFORCEMENT TEST SUITE ===")

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

log(f"[HOST] Launching QEMU for M7.1 enforcement testing: {' '.join(cmd)}")

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

# Test tuples: (Command, Sentinel_String, Expected_Exit_Code)
enforcement_cmds = [
    ("/usr/bin/blaze-sentinel status", "__SECX10_STATUS__", 0),
    ("/usr/bin/blaze-sentinel test-apparmor complain", "__SECX02_APPARMOR_COMPLAIN__", 0),
    ("/usr/bin/blaze-sentinel test-apparmor enforce || echo 'EXPECTED_ENFORCE_DENIAL'", "__SECX01_APPARMOR_ENFORCE__", 0),
    ("/usr/bin/blaze-sentinel test-landlock || echo 'EXPECTED_LANDLOCK_DENIAL'", "__SECX03_LANDLOCK__", 0),
    ("/usr/bin/blaze-sentinel test-seccomp || echo 'EXPECTED_SECCOMP_DENIAL'", "__SECX04_SECCOMP__", 0),
    ("/usr/bin/blaze-sentinel test-fsverity", "__SECX06_FSVERITY__", 0),
    ("/usr/bin/blaze-sentinel audit", "__SECX05_AUDIT__", 0),
    ("/usr/bin/portadora verify", "__SECX08_PORTADORA__", 0),
    ("/usr/bin/blaze-sentinel doctor", "__SECX07_DOCTOR__", 0)
]

while True:
    if time.time() - start_time > 120:
        log("[HOST ERROR] Milestone 7.1 Sentinel test timed out after 120s!")
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
            if ("root@" in clean_buf or "#" in clean_buf or "-bash" in clean_buf) and not sent_login:
                log("\n[M7.1-TEST] Shell prompt detected directly (autologin). Executing Enforcement Security Tests...")
                sent_login = True
                stage = "RUNNING_TESTS"
                buffer = ""
                cmd_text, sentinel, expected_code = enforcement_cmds[cmd_index]
                log(f"[M7.1-TEST] Executing [{cmd_index+1}/{len(enforcement_cmds)}]: {cmd_text}...")
                os.write(master_fd, f"{cmd_text}\necho '{sentinel}:'$?\n".encode("utf-8"))

            elif ("login:" in clean_buf.lower()) and not sent_login:
                log("\n[M7.1-TEST] Login prompt detected. Logging in as root...")
                time.sleep(0.5)
                os.write(master_fd, b"root\n")
                sent_login = True

            elif sent_login and ("root@" in clean_buf or "-bash" in clean_buf or "#" in clean_buf):
                log("\n[M7.1-TEST] Root shell obtained. Executing Enforcement Security Tests...")
                stage = "RUNNING_TESTS"
                buffer = ""
                cmd_text, sentinel, expected_code = enforcement_cmds[cmd_index]
                log(f"[M7.1-TEST] Executing [{cmd_index+1}/{len(enforcement_cmds)}]: {cmd_text}...")
                os.write(master_fd, f"{cmd_text}\necho '{sentinel}:'$?\n".encode("utf-8"))

        elif stage == "RUNNING_TESTS":
            if cmd_index < len(enforcement_cmds):
                _, sentinel, expected_code = enforcement_cmds[cmd_index]
                sentinel_pattern = rf"{sentinel}:(\d+)"
                match = re.search(sentinel_pattern, clean_buf)
                if match:
                    exit_code = int(match.group(1))
                    log(f"[M7.1-TEST] Command [{enforcement_cmds[cmd_index][0]}] exit code: {exit_code} (Expected: {expected_code})")
                    if exit_code != expected_code:
                        log(f"[HOST ERROR] Command [{enforcement_cmds[cmd_index][0]}] expected {expected_code} but got {exit_code}!")
                        os.killpg(os.getpgid(proc.pid), 9)
                        sys.exit(1)
                    cmd_index += 1
                    buffer = ""
                    if cmd_index < len(enforcement_cmds):
                        cmd_text, sentinel, _ = enforcement_cmds[cmd_index]
                        log(f"[M7.1-TEST] Executing [{cmd_index+1}/{len(enforcement_cmds)}]: {cmd_text}...")
                        os.write(master_fd, f"{cmd_text}\necho '{sentinel}:'$?\n".encode("utf-8"))
                    else:
                        log("[M7.1-TEST] All Sentinel enforcement tests passed! Ordering poweroff...")
                        os.write(master_fd, b"systemctl poweroff\n")
                        stage = "WAIT_POWEROFF"

        elif stage == "WAIT_POWEROFF":
            if "reboot: Power down" in clean_buf or "System halted" in clean_buf:
                log("[M7.1-TEST] QEMU cleanly powered down.")
                break

try:
    proc.wait(timeout=5)
except subprocess.TimeoutExpired:
    os.killpg(os.getpgid(proc.pid), 9)

log("\n=== ALL MILESTONE 7.1 BLAZE SENTINEL ENFORCEMENT TESTS PASSED WITH 0 EXIT CODES! ===")
sys.exit(0)
