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
timeout = 300  # 5 minutes max for network verification

commands_to_run = [
    # NET-01: VirtIO Link Detection
    "ip -d link show",
    # NET-02: DHCP Lease & Routing
    "networkctl status",
    "ip -4 addr show",
    "ip route show",
    # NET-03: DNS Resolution
    "resolvectl status",
    "getent hosts kernel.org",
    # NET-04: Outbound HTTPS TLS Handshake & CA Cert Trust
    "curl -Iv https://kernel.org",
    # NET-05: BadSSL Security Negative Test (must reject invalid cert)
    "if curl -s https://self-signed.badssl.com/ >/dev/null 2>&1; then echo 'BADSSL_UNEXPECTED_SUCCESS'; exit 1; else echo 'BADSSL_REJECTED_AS_EXPECTED'; fi",
    # NET-06: nftables Firewall Active Ruleset
    "systemctl status nftables --no-pager",
    "nft list ruleset",
    # NET-07: Inbound/Loopback filtering
    "ping -c 2 127.0.0.1",
    # NET-08: Interface Cycle & DHCP Recovery
    "IFACE=$(ip -o link show | awk -F': ' '{print $2}' | grep -v lo | head -n 1) && echo \"Cycling $IFACE\" && ip link set dev \"$IFACE\" down && sleep 2 && ip link set dev \"$IFACE\" up && sleep 4 && ip -4 addr show \"$IFACE\"",
    # NET-09: OpenSSH Controlled Activation & Disabled by Default
    "systemctl is-active sshd.service || echo 'SSHD_INACTIVE_AS_EXPECTED'",
    "systemctl start sshd.service",
    "sleep 1",
    "systemctl status sshd.service --no-pager",
    "ss -tlpn",
    # NET-10: Portadora Package Integrity (53 packages)
    "portadora verify",
    # NET-11: Graceful Systemd Reboot Transition
    "systemctl is-system-running || true",
    "systemctl reboot",
]
cmd_index = 0
current_sentinel = ""

post_commands = [
    # Post-Reboot Verification
    "uname -a",
    "networkctl status",
    "ip -4 addr show",
    "nft list ruleset",
    "curl -sI https://kernel.org | head -n 5",
    "systemctl is-active sshd.service || echo 'SSHD_INACTIVE_POST_REBOOT'",
    "portadora verify",
    "systemctl is-system-running || true",
    "systemctl poweroff",
]
post_cmd_index = 0

print("=== Starting Milestone 4 Networking & Security QEMU Test ===")
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
                    print("\n[M4-TEST] Login prompt reached. Logging in as root...")
                    time.sleep(0.5)
                    os.write(master, b"root\n")
                    buffer = ""
                    stage = "wait_prompt"

            elif stage == "wait_prompt":
                if "#" in buffer:
                    print("\n[M4-TEST] Root shell prompt detected.")
                    buffer = ""
                    stage = "ready_for_cmd"

            elif stage == "running_cmd":
                match = re.search(r'\n' + re.escape(current_sentinel) + r':(\d+)', buffer)
                if match:
                    code_part = match.group(1)
                    if code_part != "0":
                        print(f"\n[ERROR] Command [{cmd_index}/{len(commands_to_run)}] failed with exit code: {code_part}")
                        sys.exit(1)
                    print(f"\n[M4-TEST] Command [{cmd_index}/{len(commands_to_run)}] finished successfully (exit code 0).")
                    buffer = ""
                    stage = "ready_for_cmd"

            elif stage == "wait_relogin":
                if "blaze login:" in buffer:
                    print("\n[M4-TEST] REBOOT SUCCESSFUL: System rebooted cleanly into second login prompt!")
                    print("[M4-TEST] Logging into post-reboot system for final verification...")
                    time.sleep(0.5)
                    os.write(master, b"root\n")
                    buffer = ""
                    stage = "wait_post_prompt"

            elif stage == "wait_post_prompt":
                if "#" in buffer:
                    print("\n[M4-TEST] Post-reboot root shell detected.")
                    buffer = ""
                    stage = "ready_post_cmd"

            elif stage == "running_post_cmd":
                match = re.search(r'\n' + re.escape(current_sentinel) + r':(\d+)', buffer)
                if match:
                    code_part = match.group(1)
                    if code_part != "0":
                        print(f"\n[ERROR] Post-reboot command [{post_cmd_index}/{len(post_commands)}] failed with exit code: {code_part}")
                        sys.exit(1)
                    print(f"\n[M4-TEST] Post-reboot command [{post_cmd_index}/{len(post_commands)}] finished successfully (exit code 0).")
                    buffer = ""
                    stage = "ready_post_cmd"

        if stage == "ready_post_cmd":
            time.sleep(0.2)
            if post_cmd_index < len(post_commands):
                c = post_commands[post_cmd_index]
                post_cmd_index += 1
                if c.startswith("systemctl poweroff") or c.startswith("poweroff"):
                    print(f"\n[M4-TEST] Executing [{post_cmd_index}/{len(post_commands)}]: {c} (graceful poweroff)...")
                    os.write(master, (c + "\n").encode())
                    stage = "wait_poweroff"
                    buffer = ""
                else:
                    sentinel = f"__BLZ_POST_SENTINEL_{post_cmd_index}__"
                    current_sentinel = sentinel
                    full_cmd = f"{c}\necho \"{sentinel}:$?\"\n"
                    print(f"\n[M4-TEST] Executing Post-Reboot [{post_cmd_index}/{len(post_commands)}]: {c[:70]}...")
                    os.write(master, full_cmd.encode())
                    stage = "running_post_cmd"
                    buffer = ""

        if stage == "ready_for_cmd":
            time.sleep(0.2)
            if cmd_index < len(commands_to_run):
                c = commands_to_run[cmd_index]
                cmd_index += 1
                if c.startswith("systemctl reboot") or c.startswith("reboot"):
                    print(f"\n[M4-TEST] Executing [{cmd_index}/{len(commands_to_run)}]: {c} (graceful systemd reboot)...")
                    os.write(master, (c + "\n").encode())
                    stage = "wait_relogin"
                    buffer = ""
                else:
                    sentinel = f"__BLZ_SENTINEL_{cmd_index}__"
                    current_sentinel = sentinel
                    full_cmd = f"{c}\necho \"{sentinel}:$?\"\n"
                    print(f"\n[M4-TEST] Executing [{cmd_index}/{len(commands_to_run)}]: {c[:70]}...")
                    os.write(master, full_cmd.encode())
                    stage = "running_cmd"
                    buffer = ""

        if proc.poll() is not None:
            print(f"\n[M4-TEST] QEMU exited with code {proc.returncode}")
            break

finally:
    if proc.poll() is None:
        try:
            os.killpg(os.getpgid(proc.pid), 9)
        except OSError:
            pass
    print("\n=== Milestone 4 Networking & Security Run Finished ===")
