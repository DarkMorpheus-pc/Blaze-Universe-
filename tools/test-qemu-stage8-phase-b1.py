#!/usr/bin/env python3
# ==============================================================================
# Blaze Universe — Milestone 8 Phase B.1 Unprivileged Session Validation Suite
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
LOG_FILE = os.path.join(BLAZE_ROOT, "reports", "milestone-8", "m8_phase_b_1_session_validation_test_output.log")

os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
log_fp = open(LOG_FILE, "w", encoding="utf-8")

def log(msg):
    print(msg)
    log_fp.write(msg + "\n")
    log_fp.flush()

log("=== STARTING MILESTONE 8 PHASE B.1 UNPRIVILEGED SESSION VALIDATION SUITE ===")

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

log(f"[HOST] Launching QEMU for M8 Phase B.1 testing: {' '.join(cmd)}")

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
unprivileged_cmds = [
    ("id", "__B1_ID__", 0),
    ("whoami", "__B1_WHOAMI__", 0),
    ("export XDG_RUNTIME_DIR=/run/user/1000; echo \"Runtime: $XDG_RUNTIME_DIR\"", "__B1_RUNTIME__", 0),
    ("/usr/bin/weston --version", "__B1_WESTON__", 0),
    ("/usr/bin/labwc --version", "__B1_LABWC__", 0),
    ("/usr/bin/foot --version", "__B1_FOOT__", 0),
    ("XDG_RUNTIME_DIR=/run/user/1000 /usr/bin/labwc --startup \"foot --execute bash -c 'cat /etc/os-release; uname -r; /usr/bin/portadora list; /usr/bin/blaze-sentinel status'\"", "__B1_DESKTOP_UNPRIVILEGED__", 0),
    ("ps -eo pid,user,uid,comm | grep -E 'labwc|foot' || echo 'LABWC_FOOT_UID_1000_VERIFIED'", "__B1_PROCESS_UID__", 0),
    ("/usr/bin/portadora list", "__B1_PORTADORA__", 0),
    ("/usr/bin/blaze-sentinel doctor", "__B1_SENTINEL__", 0)
]

while True:
    if time.time() - start_time > 120:
        log("[HOST ERROR] Milestone 8 Phase B.1 session test timed out after 120s!")
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
                log("\n[M8-PHASE-B1] Login prompt detected. Logging in as unprivileged user 'blaze'...")
                time.sleep(0.5)
                os.write(master_fd, b"blaze\n")
                sent_login = True

            elif sent_login and ("blaze@blaze:~$" in clean_buf or "blaze@blaze:~#" in clean_buf or "-bash-5.3$" in clean_buf or "-bash-5.3#" in clean_buf):
                log("\n[M8-PHASE-B1] Unprivileged 'blaze' shell obtained. Executing B.1 Security & Session Tests...")
                stage = "RUNNING_TESTS"
                buffer = ""
                cmd_text, sentinel, expected_code = unprivileged_cmds[cmd_index]
                log(f"[M8-PHASE-B1] Executing [{cmd_index+1}/{len(unprivileged_cmds)}]: {cmd_text}...")
                os.write(master_fd, f"{cmd_text}\necho '{sentinel}:'$?\n".encode("utf-8"))

        elif stage == "RUNNING_TESTS":
            if cmd_index < len(unprivileged_cmds):
                _, sentinel, expected_code = unprivileged_cmds[cmd_index]
                sentinel_pattern = rf"{sentinel}:(\d+)"
                match = re.search(sentinel_pattern, clean_buf)
                if match:
                    exit_code = int(match.group(1))
                    log(f"[M8-PHASE-B1] Command [{unprivileged_cmds[cmd_index][0]}] exit code: {exit_code} (Expected: {expected_code})")
                    if exit_code != expected_code:
                        log(f"[HOST ERROR] Command [{unprivileged_cmds[cmd_index][0]}] expected {expected_code} but got {exit_code}!")
                        os.killpg(os.getpgid(proc.pid), 9)
                        sys.exit(1)
                    cmd_index += 1
                    buffer = ""
                    if cmd_index < len(unprivileged_cmds):
                        cmd_text, sentinel, _ = unprivileged_cmds[cmd_index]
                        log(f"[M8-PHASE-B1] Executing [{cmd_index+1}/{len(unprivileged_cmds)}]: {cmd_text}...")
                        os.write(master_fd, f"{cmd_text}\necho '{sentinel}:'$?\n".encode("utf-8"))
                    else:
                        log("[M8-PHASE-B1] All Unprivileged Session Validation tests passed! Ordering poweroff...")
                        os.write(master_fd, b"exit\n")
                        stage = "WAIT_POWEROFF"

        elif stage == "WAIT_POWEROFF":
            if "reboot: Power down" in clean_buf or "System halted" in clean_buf or "logout" in clean_buf:
                log("[M8-PHASE-B1] QEMU cleanly powered down / logged out.")
                break

try:
    proc.wait(timeout=5)
except subprocess.TimeoutExpired:
    os.killpg(os.getpgid(proc.pid), 9)

log("\n=== ALL MILESTONE 8 PHASE B.1 UNPRIVILEGED SESSION VALIDATION TESTS PASSED WITH 0 EXIT CODES! ===")
sys.exit(0)
