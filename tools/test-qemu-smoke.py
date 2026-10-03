#!/usr/bin/env python3
import os
import pty
import select
import subprocess
import sys
import time

BLAZE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DISK_IMG = os.path.join(BLAZE_ROOT, "build", "blaze-disk.raw")
OVMF_CODE = "/usr/share/edk2/x64/OVMF.4m.fd"

cmd = [
    "qemu-system-x86_64",
    "-bios", OVMF_CODE,
    "-drive", f"file={DISK_IMG},format=raw,if=virtio",
    "-m", "8G",
    "-smp", "8",
    "-nographic",
    "-serial", "stdio",
    "-monitor", "none",
]

if os.access("/dev/kvm", os.R_OK | os.W_OK):
    cmd.extend(["-enable-kvm", "-cpu", "host"])

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

buffer = ""
stage = "wait_login"
start_time = time.time()
timeout = 90

commands_to_run = [
    "uname -a",
    "cat /etc/os-release",
    "systemctl is-system-running",
    "portadora list",
    "portadora verify",
    "reboot -f",
]
cmd_index = 0
last_cmd_time = 0

print("=== Starting Automated QEMU Smoke Test for Blaze Native v0.1 ===")
sys.stdout.flush()

try:
    while time.time() - start_time < timeout:
        r, _, _ = select.select([master], [], [], 0.2)
        if r:
            try:
                data = os.read(master, 1024).decode("utf-8", errors="replace")
            except OSError:
                break
            if not data:
                break
            sys.stdout.write(data)
            sys.stdout.flush()
            buffer += data

            if stage == "wait_login":
                if "blaze login:" in buffer:
                    print("\n[SMOKE] Detected login prompt. Sending 'root'...")
                    time.sleep(0.5)
                    os.write(master, b"root\n")
                    buffer = ""
                    stage = "logged_in"
                    last_cmd_time = time.time()

        if stage == "wait_relogin" and "blaze login:" in buffer:
            print("\n[SMOKE] REBOOT OK: login prompt returned.")
            break

        if stage == "logged_in" and (time.time() - last_cmd_time > 2.0):
            if cmd_index < len(commands_to_run):
                c = commands_to_run[cmd_index]
                print(f"\n[SMOKE] Executing: {c}")
                os.write(master, (c + "\n").encode())
                cmd_index += 1
                last_cmd_time = time.time()
            else:
                print("\n[SMOKE] Reboot dispatched. Waiting for second login prompt...")
                stage = "wait_relogin"
                buffer = ""

        if proc.poll() is not None:
            print(f"\n[SMOKE] QEMU exited with code {proc.returncode}")
            break

finally:
    if proc.poll() is None:
        try:
            os.killpg(os.getpgid(proc.pid), 9)
        except Exception:
            pass
    os.close(master)

print("\n=== QEMU Smoke Test Finished ===")
