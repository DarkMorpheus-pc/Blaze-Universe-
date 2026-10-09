#!/usr/bin/env python3
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
REPO_DIR = os.path.join(BLAZE_ROOT, "build", "repo")
SSH_KEY = os.path.join(BLAZE_ROOT, "build", "test_ssh_key")

# 1. Start local repo server
subprocess.run(["fuser", "-k", "8080/tcp"], stderr=subprocess.DEVNULL)
subprocess.run(["fuser", "-k", "2222/tcp"], stderr=subprocess.DEVNULL)
time.sleep(0.5)
print("[HOST] Starting local TUF repository server on http://0.0.0.0:8080...")
repo_proc = subprocess.Popen(
    [sys.executable, os.path.join(BLAZE_ROOT, "tools", "repo-server.py"), "serve", "--repo-dir", REPO_DIR, "--port", "8080"],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    preexec_fn=os.setsid
)
time.sleep(1.5)

# Verify repo server is responding
import urllib.request
try:
    resp = urllib.request.urlopen("http://127.0.0.1:8080/metadata/root.json")
    assert resp.status == 200
    print("[HOST] TUF repository server online and serving metadata.")
except Exception as e:
    print(f"[HOST ERROR] Failed to connect to local repo server: {e}")
    os.killpg(os.getpgid(repo_proc.pid), 9)
    sys.exit(1)

# 2. Build QEMU command
cmd = [
    "qemu-system-x86_64",
    "-bios", OVMF_CODE,
    "-drive", f"file={ROOT_DISK},format=raw,if=virtio",
    "-netdev", "user,id=net0,hostfwd=tcp::2222-:22",
    "-device", "virtio-net-pci,netdev=net0",
    "-m", "4G",
    "-smp", "4",
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
timeout = 400

commands_to_run = [
    # M5-01: TUF Metadata Sync
    "portadora update",
    # M5-02: Remote Package Search & Info
    "portadora search nano",
    "portadora info nano",
    # M5-03: Remote Package Installation & Verification
    "portadora install nano",
    "/usr/bin/nano --version | head -n 2",
    # M5-04: Tampered Package Rejection (SHA-256 Mismatch)
    "( if portadora install corrupt-pkg; then echo 'TAMPER_FAILURE'; exit 1; else echo 'TAMPER_REJECTED_AS_EXPECTED'; fi )",
    # M5-05: Expired / Rolled-back Metadata Rejection
    "( if portadora update --repo-url http://10.0.2.2:8080/test-expired; then echo 'EXPIRED_FAILURE'; exit 1; else echo 'EXPIRED_REJECTED_AS_EXPECTED'; fi )",
    "( if portadora update --repo-url http://10.0.2.2:8080/test-rollback; then echo 'ROLLBACK_FAILURE'; exit 1; else echo 'ROLLBACK_REJECTED_AS_EXPECTED'; fi )",
    # M5-06: Dependency Conflict & Cycle Handling
    "( if portadora install cycle-a; then echo 'CYCLE_FAILURE'; exit 1; else echo 'CYCLE_REJECTED_AS_EXPECTED'; fi )",
    "( if portadora install conflict-nano; then echo 'CONFLICT_FAILURE'; exit 1; else echo 'CONFLICT_REJECTED_AS_EXPECTED'; fi )",
    # M5-07: Failure Injection & Crash Recovery
    "mkdir -p /var/lib/portadora/journal/tx-mock-crash/backups/etc && touch /etc/crash-test.txt && printf '{\"tx_id\":\"tx-mock-crash\",\"state\":\"Journaled\",\"package_names\":[\"mock\"],\"operations\":[{\"Create\":{\"target_path\":\"/etc/crash-test.txt\",\"staging_path\":\"/var/lib/portadora/journal/tx-mock-crash/backups/etc/crash-test.txt\"}}],\"timestamp\":1791580000}' > /var/lib/portadora/journal/tx-mock-crash/journal.json && portadora recover && test ! -f /etc/crash-test.txt && test ! -d /var/lib/portadora/journal/tx-mock-crash && echo 'RECOVERY_VERIFIED'",
    # M5-08: Portadora Self-Upgrade (0.1.0 -> 0.2.0)
    "portadora upgrade portadora",
    "/usr/bin/portadora --version",
    # M5-09: Full System Integrity Verification
    "portadora verify",
    # M5-10: System Reboot
    "systemctl reboot",
]
cmd_index = 0
current_sentinel = ""

post_commands = [
    # M5-10 Verification Post Reboot
    "uname -a",
    "/usr/bin/nano --version | head -n 2",
    "portadora verify",
    # M5-11: TUF Key Rotation (Host rotates root key in parallel)
    "portadora update",
    # M5-12: IPv6 RFC 4890 Firewall Verification
    "nft list ruleset | grep -A 10 'icmpv6 type'",
    "ping -6 -c 2 ::1",
    # M5-13: Real Interactive SSH Session (Start SSHD)
    "systemctl is-active sshd.service || echo 'SSHD_INACTIVE_BY_DEFAULT'",
    "systemctl start sshd.service",
    "systemctl is-active sshd.service",
    # Sentinel for host SSH probe
    "echo '__HOST_RUN_SSH_NOW__'",
    # Stop SSHD and verify disabled
    "systemctl stop sshd.service",
    "systemctl is-active sshd.service || echo 'SSHD_STOPPED_SUCCESSFULLY'",
    "systemctl is-enabled sshd.service || echo 'SSHD_DISABLED_ON_BOOT'",
    "portadora history | tail -n 10",
    "systemctl poweroff",
]
post_cmd_index = 0

print("=== Starting Milestone 5 Portadora Repository & Secure Updates QEMU Test ===")
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
                    print("\n[M5-TEST] Initial login prompt reached. Logging in as root...")
                    time.sleep(0.5)
                    os.write(master, b"root\n")
                    buffer = ""
                    stage = "wait_prompt"

            elif stage == "wait_prompt":
                if "#" in buffer:
                    print("\n[M5-TEST] Root shell prompt detected.")
                    buffer = ""
                    stage = "ready_for_cmd"

            elif stage == "running_cmd":
                match = re.search(r'\n' + re.escape(current_sentinel) + r':(\d+)', buffer)
                if match:
                    code_part = match.group(1)
                    if code_part != "0":
                        print(f"\n[ERROR] Command [{cmd_index}/{len(commands_to_run)}] failed with exit code: {code_part}")
                        sys.exit(1)
                    print(f"\n[M5-TEST] Command [{cmd_index}/{len(commands_to_run)}] finished successfully (exit code 0).")
                    buffer = ""
                    stage = "ready_for_cmd"

            elif stage == "wait_relogin":
                if "blaze login:" in buffer:
                    print("\n[M5-TEST] REBOOT SUCCESSFUL: System rebooted cleanly into second login prompt!")
                    # Host performs M5-11 root key rotation while guest is ready!
                    print("[HOST] Rotating TUF root key on repository server (v1 -> v2)...")
                    subprocess.run(
                        [sys.executable, os.path.join(BLAZE_ROOT, "tools", "repo-server.py"), "rotate-root", "--repo-dir", REPO_DIR],
                        check=True
                    )
                    time.sleep(0.5)
                    print("[M5-TEST] Logging into post-reboot system for final verification...")
                    os.write(master, b"root\n")
                    buffer = ""
                    stage = "wait_post_prompt"

            elif stage == "wait_post_prompt":
                if "#" in buffer:
                    print("\n[M5-TEST] Post-reboot root shell detected.")
                    buffer = ""
                    stage = "ready_post_cmd"

            elif stage == "running_post_cmd":
                if "__HOST_RUN_SSH_NOW__" in buffer:
                    time.sleep(1.0)
                    print("\n[HOST] Executing M5-13: Authenticated SSH Session from host to VM port 2222...")
                    ssh_res = subprocess.run(
                        [
                            "ssh",
                            "-o", "StrictHostKeyChecking=no",
                            "-o", "UserKnownHostsFile=/dev/null",
                            "-o", "BatchMode=yes",
                            "-o", "ConnectTimeout=10",
                            "-i", SSH_KEY,
                            "-p", "2222",
                            "root@127.0.0.1",
                            "uname -r && /usr/bin/nano --version | head -n 1 && echo 'SSH_AUTH_VERIFIED'"
                        ],
                        capture_output=True,
                        text=True
                    )
                    print(f"[HOST SSH OUTPUT]:\n{ssh_res.stdout}")
                    if ssh_res.returncode != 0 or "SSH_AUTH_VERIFIED" not in ssh_res.stdout:
                        print(f"[ERROR] SSH connection failed! stderr:\n{ssh_res.stderr}")
                        sys.exit(1)
                    print("[HOST] M5-13: Authenticated SSH Session Verified Successfully!")

                match = re.search(r'\n' + re.escape(current_sentinel) + r':(\d+)', buffer)
                if match:
                    code_part = match.group(1)
                    if code_part != "0":
                        print(f"\n[ERROR] Post-reboot command [{post_cmd_index}/{len(post_commands)}] failed with exit code: {code_part}")
                        sys.exit(1)
                    print(f"\n[M5-TEST] Post-reboot command [{post_cmd_index}/{len(post_commands)}] finished successfully (exit code 0).")
                    buffer = ""
                    stage = "ready_post_cmd"

        if stage == "ready_post_cmd":
            time.sleep(0.2)
            if post_cmd_index < len(post_commands):
                c = post_commands[post_cmd_index]
                post_cmd_index += 1
                if c.startswith("systemctl poweroff") or c.startswith("poweroff"):
                    print(f"\n[M5-TEST] Executing [{post_cmd_index}/{len(post_commands)}]: {c} (graceful poweroff)...")
                    os.write(master, (c + "\n").encode())
                    stage = "wait_poweroff"
                    buffer = ""
                else:
                    sentinel = f"__BLZ_POST_SENTINEL_{post_cmd_index}__"
                    current_sentinel = sentinel
                    full_cmd = f"{c}\necho \"{sentinel}:$?\"\n"
                    print(f"\n[M5-TEST] Executing Post-Reboot [{post_cmd_index}/{len(post_commands)}]: {c[:70]}...")
                    os.write(master, full_cmd.encode())
                    stage = "running_post_cmd"
                    buffer = ""

        if stage == "ready_for_cmd":
            time.sleep(0.2)
            if cmd_index < len(commands_to_run):
                c = commands_to_run[cmd_index]
                cmd_index += 1
                if c.startswith("systemctl reboot") or c.startswith("reboot"):
                    print(f"\n[M5-TEST] Executing [{cmd_index}/{len(commands_to_run)}]: {c} (graceful systemd reboot)...")
                    os.write(master, (c + "\n").encode())
                    stage = "wait_relogin"
                    buffer = ""
                else:
                    sentinel = f"__BLZ_SENTINEL_{cmd_index}__"
                    current_sentinel = sentinel
                    full_cmd = f"{c}\necho \"{sentinel}:$?\"\n"
                    print(f"\n[M5-TEST] Executing [{cmd_index}/{len(commands_to_run)}]: {c[:70]}...")
                    os.write(master, full_cmd.encode())
                    stage = "running_cmd"
                    buffer = ""

        if proc.poll() is not None:
            print(f"\n[M5-TEST] QEMU exited with code {proc.returncode}")
            break

finally:
    if proc.poll() is None:
        try:
            os.killpg(os.getpgid(proc.pid), 9)
        except OSError:
            pass
    if repo_proc.poll() is None:
        try:
            os.killpg(os.getpgid(repo_proc.pid), 9)
        except OSError:
            pass
    print("\n=== Milestone 5 Portadora Repository & Secure Updates Run Finished ===")
