#!/usr/bin/env python3
import os
import pty
import select
import subprocess
import sys
import time

BLAZE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ROOT_DISK = os.path.join(BLAZE_ROOT, "build", "blaze-disk.raw")
BUILD_DISK = os.path.join(BLAZE_ROOT, "build", "blaze-build-disk.raw")
OVMF_CODE = "/usr/share/edk2/x64/OVMF.4m.fd"

cmd = [
    "qemu-system-x86_64",
    "-bios", OVMF_CODE,
    "-drive", f"file={ROOT_DISK},format=raw,if=virtio",
    "-drive", f"file={BUILD_DISK},format=raw,if=virtio",
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
timeout = 2400  # 40 minutes max for full in-VM Gen1 + Gen2 + Rust toolchain compilation

commands_to_run = [
    "uname -a",
    "cat /etc/os-release",
    "df -h",
    "ls -la /build",
    "/build/stage3-runner.sh",
    "cat /build/reports/gen1_gen2_comparison.txt",
    "cat /build/reports/rust_bootstrap_provenance.txt",
    "cat /usr/share/blazeos/selfhost_token.txt",
    "systemctl is-system-running || true",
    "reboot -f",
]
cmd_index = 0
current_sentinel = ""

post_commands = [
    "uname -a",
    "portadora verify",
    "cat /usr/share/blazeos/selfhost_token.txt",
    "systemctl is-system-running || true",
    "poweroff -f",
]
post_cmd_index = 0

print("=== Starting Milestone 3 Full Self-Hosting QEMU Execution ===")
sys.stdout.flush()

try:
    while time.time() - start_time < timeout:
        r, _, _ = select.select([master], [], [], 0.1)
        if r:
            try:
                data = os.read(master, 4096).decode("utf-8", errors="replace")
            except OSError:
                break
            if not data:
                break
            sys.stdout.write(data)
            sys.stdout.flush()
            buffer += data

            if stage == "wait_login":
                if "blaze login:" in buffer:
                    print("\n[STAGE3] Login prompt reached. Logging in as root...")
                    time.sleep(0.5)
                    os.write(master, b"root\n")
                    buffer = ""
                    stage = "wait_prompt"

            elif stage == "wait_prompt":
                if "#" in buffer:
                    print("\n[STAGE3] Root shell prompt detected.")
                    buffer = ""
                    stage = "ready_for_cmd"

            elif stage == "running_cmd":
                import re
                match = re.search(r'\n' + re.escape(current_sentinel) + r':(\d+)', buffer)
                if match:
                    code_part = match.group(1)
                    if code_part != "0":
                        print(f"\n[ERROR] Command [{cmd_index}/{len(commands_to_run)}] failed with exit code: {code_part}")
                        sys.exit(1)
                    print(f"\n[STAGE3] Command [{cmd_index}/{len(commands_to_run)}] finished successfully (exit code 0).")
                    buffer = ""
                    stage = "ready_for_cmd"

            elif stage == "wait_relogin":
                if "blaze login:" in buffer:
                    print("\n[STAGE3] REBOOT SUCCESSFUL: System rebooted cleanly into second login prompt!")
                    print("[STAGE3] Logging into post-reboot system for final verification...")
                    time.sleep(0.5)
                    os.write(master, b"root\n")
                    buffer = ""
                    stage = "wait_post_prompt"

            elif stage == "wait_post_prompt":
                if "#" in buffer:
                    print("\n[STAGE3] Post-reboot root shell detected.")
                    buffer = ""
                    stage = "ready_post_cmd"

            elif stage == "running_post_cmd":
                import re
                match = re.search(r'\n' + re.escape(current_sentinel) + r':(\d+)', buffer)
                if match:
                    code_part = match.group(1)
                    if code_part != "0":
                        print(f"\n[ERROR] Post-reboot command [{post_cmd_index}/{len(post_commands)}] failed with exit code: {code_part}")
                        sys.exit(1)
                    print(f"\n[STAGE3] Post-reboot command [{post_cmd_index}/{len(post_commands)}] finished successfully (exit code 0).")
                    buffer = ""
                    stage = "ready_post_cmd"

        if stage == "ready_post_cmd":
            time.sleep(0.2)
            if post_cmd_index < len(post_commands):
                c = post_commands[post_cmd_index]
                post_cmd_index += 1
                if c.startswith("poweroff"):
                    print(f"\n[STAGE3] Executing [{post_cmd_index}/{len(post_commands)}]: {c} (clean shutdown)...")
                    os.write(master, (c + "\n").encode())
                    stage = "wait_poweroff"
                    buffer = ""
                else:
                    sentinel = f"__BLZ_POST_SENTINEL_{post_cmd_index}__"
                    current_sentinel = sentinel
                    full_cmd = f"{c}\necho \"{sentinel}:$?\"\n"
                    print(f"\n[STAGE3] Executing Post-Reboot [{post_cmd_index}/{len(post_commands)}]: {c[:70]}...")
                    os.write(master, full_cmd.encode())
                    stage = "running_post_cmd"
                    buffer = ""

        if stage == "ready_for_cmd":
            time.sleep(0.2)
            if cmd_index < len(commands_to_run):
                c = commands_to_run[cmd_index]
                cmd_index += 1
                if c.startswith("reboot"):
                    print(f"\n[STAGE3] Executing [{cmd_index}/{len(commands_to_run)}]: {c} (final reboot)...")
                    os.write(master, (c + "\n").encode())
                    stage = "wait_relogin"
                    buffer = ""
                else:
                    sentinel = f"__BLZ_SENTINEL_{cmd_index}__"
                    current_sentinel = sentinel
                    full_cmd = f"{c}\necho \"{sentinel}:$?\"\n"
                    print(f"\n[STAGE3] Executing [{cmd_index}/{len(commands_to_run)}]: {c[:70]}...")
                    os.write(master, full_cmd.encode())
                    stage = "running_cmd"
                    buffer = ""

        if proc.poll() is not None:
            print(f"\n[STAGE3] QEMU exited with code {proc.returncode}")
            break

finally:
    if proc.poll() is None:
        try:
            os.killpg(os.getpgid(proc.pid), 9)
        except OSError:
            pass
    print("\n=== Milestone 3 Execution Run Finished ===")
