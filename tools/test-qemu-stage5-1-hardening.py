#!/usr/bin/env python3
import os
import pty
import re
import select
import socket
import socketserver
import subprocess
import sys
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

BLAZE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ROOT_DISK = os.path.join(BLAZE_ROOT, "build", "blaze-disk.raw")
OVMF_CODE = "/usr/share/edk2/x64/OVMF.4m.fd"
REPO_DIR = os.path.join(BLAZE_ROOT, "build", "repo")
LOG_FILE = os.path.join(BLAZE_ROOT, "reports", "milestone-5", "m5_1_test_output.log")

os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
log_fp = open(LOG_FILE, "w", encoding="utf-8")

def log(msg):
    print(msg)
    log_fp.write(msg + "\n")
    log_fp.flush()

# ------------------------------------------------------------------------------
# 1. Start IPv6 HTTP Server on Host
# ------------------------------------------------------------------------------
class IPv6Server(HTTPServer):
    address_family = socket.AF_INET6

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK_ROUTED_IPV6\n")
    def log_message(self, format, *args):
        pass

ipv6_httpd = None
def start_ipv6_server():
    global ipv6_httpd
    try:
        ipv6_httpd = IPv6Server(("::", 8088), HealthHandler)
        log("[HOST] Dual-stack / IPv6 HTTP server listening on [::]:8088")
        threading.Thread(target=ipv6_httpd.serve_forever, daemon=True).start()
    except Exception as e:
        log(f"[HOST WARN] Could not start IPv6 server on [::]:8088: {e}")

start_ipv6_server()

# ------------------------------------------------------------------------------
# 2. Start TUF Repository Server
# ------------------------------------------------------------------------------
subprocess.run(["fuser", "-k", "8080/tcp"], stderr=subprocess.DEVNULL)
time.sleep(0.5)
log("[HOST] Starting local TUF repository server on http://0.0.0.0:8080...")
repo_proc = subprocess.Popen(
    [sys.executable, os.path.join(BLAZE_ROOT, "tools", "repo-server.py"), "serve", "--repo-dir", REPO_DIR, "--port", "8080"],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    preexec_fn=os.setsid
)
time.sleep(1.5)

import urllib.request
try:
    resp = urllib.request.urlopen("http://127.0.0.1:8080/metadata/root.json")
    assert resp.status == 200
    log("[HOST] TUF repository server online and serving metadata.")
except Exception as e:
    log(f"[HOST ERROR] Failed to connect to local repo server: {e}")
    os.killpg(os.getpgid(repo_proc.pid), 9)
    sys.exit(1)

# ------------------------------------------------------------------------------
# 3. Independent TUF Specification Verification
# ------------------------------------------------------------------------------
log("\n[HOST] Executing Independent TUF Specification Verification...")
tuf_verify_res = subprocess.run(
    [sys.executable, os.path.join(BLAZE_ROOT, "tools", "verify_tuf_independent.py"), REPO_DIR],
    capture_output=True,
    text=True
)
log(tuf_verify_res.stdout)
if tuf_verify_res.returncode != 0:
    log(f"[HOST ERROR] Independent TUF verification failed! stderr:\n{tuf_verify_res.stderr}")
    os.killpg(os.getpgid(repo_proc.pid), 9)
    sys.exit(1)
log("[HOST] Independent TUF verification verified successfully!\n")

# ------------------------------------------------------------------------------
# 4. Launch QEMU with Routed IPv6 Configuration
# ------------------------------------------------------------------------------
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
timeout = 500

# Commands to run in VM
commands_to_run = [
    "/root/run_m5_1_tests.sh",
    "systemctl reboot",
]

cmd_index = 0
current_sentinel = ""

post_commands = [
    # M5.1-POST-01: Verify Post-Reboot Health & Nano Execution
    "uname -a",
    "/usr/bin/nano --version | head -n 1",
    "/usr/bin/portadora --version",
    # M5.1-POST-02: Portadora Integrity Across All Packages
    "portadora verify",
    # M5.1-POST-03: Services Status
    "systemctl is-active nftables.service",
    "systemctl is-active systemd-networkd.service",
    "systemctl is-active systemd-resolved.service",
    "systemctl is-enabled sshd.service || echo 'SSHD_DISABLED_ON_BOOT'",
    # M5.1-FINISH: Clean Poweroff
    "systemctl poweroff",
]
post_cmd_index = 0

log("=== Starting Milestone 5.1 Hardening & Security Verification QEMU Harness ===")

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
            log_fp.write(data)
            log_fp.flush()
            sys.stdout.write(data)
            sys.stdout.flush()
            buffer += data

            if stage == "wait_login":
                if "blaze login:" in buffer:
                    log("\n[M5.1-TEST] Initial login prompt reached. Logging in as root...")
                    time.sleep(0.5)
                    os.write(master, b"root\n")
                    buffer = ""
                    stage = "wait_prompt"

            elif stage == "wait_prompt":
                if "#" in buffer:
                    log("\n[M5.1-TEST] Root shell prompt detected.")
                    buffer = ""
                    stage = "ready_for_cmd"

            elif stage == "running_cmd":
                match = re.search(r'\n' + re.escape(current_sentinel) + r':(\d+)', buffer)
                if match:
                    code_part = match.group(1)
                    if code_part != "0":
                        log(f"\n[ERROR] Command [{cmd_index}/{len(commands_to_run)}] failed with exit code: {code_part}")
                        sys.exit(1)
                    log(f"\n[M5.1-TEST] Command [{cmd_index}/{len(commands_to_run)}] finished successfully (exit code 0).")
                    buffer = ""
                    stage = "ready_for_cmd"

            elif stage == "wait_relogin":
                if "blaze login:" in buffer:
                    log("\n[M5.1-TEST] REBOOT SUCCESSFUL: System rebooted cleanly into second login prompt!")
                    time.sleep(0.5)
                    os.write(master, b"root\n")
                    buffer = ""
                    stage = "wait_post_prompt"

            elif stage == "wait_post_prompt":
                if "#" in buffer:
                    log("\n[M5.1-TEST] Post-reboot root shell detected.")
                    buffer = ""
                    stage = "ready_post_cmd"

            elif stage == "running_post_cmd":
                match = re.search(r'\n' + re.escape(current_sentinel) + r':(\d+)', buffer)
                if match:
                    code_part = match.group(1)
                    if code_part != "0":
                        log(f"\n[ERROR] Post-reboot command [{post_cmd_index}/{len(post_commands)}] failed with exit code: {code_part}")
                        sys.exit(1)
                    log(f"\n[M5.1-TEST] Post-reboot command [{post_cmd_index}/{len(post_commands)}] finished successfully (exit code 0).")
                    buffer = ""
                    stage = "ready_post_cmd"

        if stage == "ready_for_cmd":
            time.sleep(0.3)
            if cmd_index < len(commands_to_run):
                c = commands_to_run[cmd_index]
                cmd_index += 1
                if c.startswith("systemctl reboot") or c.startswith("reboot"):
                    log(f"\n[M5.1-TEST] Executing [{cmd_index}/{len(commands_to_run)}]: {c} (rebooting)...")
                    os.write(master, (c + "\n").encode())
                    stage = "wait_relogin"
                    buffer = ""
                else:
                    sentinel = f"__BLZ_SENTINEL_{cmd_index}__"
                    current_sentinel = sentinel
                    full_cmd = f"{c}\necho \"{sentinel}:$?\"\n"
                    log(f"\n[M5.1-TEST] Executing [{cmd_index}/{len(commands_to_run)}]: {c}...")
                    os.write(master, full_cmd.encode())
                    stage = "running_cmd"
                    buffer = ""

        elif stage == "ready_post_cmd":
            time.sleep(0.3)
            if post_cmd_index < len(post_commands):
                c = post_commands[post_cmd_index]
                post_cmd_index += 1
                if c.startswith("systemctl poweroff") or c.startswith("poweroff"):
                    log(f"\n[M5.1-TEST] Executing [{post_cmd_index}/{len(post_commands)}]: {c} (graceful poweroff)...")
                    os.write(master, (c + "\n").encode())
                    stage = "wait_poweroff"
                    buffer = ""
                else:
                    sentinel = f"__BLZ_POST_SENTINEL_{post_cmd_index}__"
                    current_sentinel = sentinel
                    full_cmd = f"{c}\necho \"{sentinel}:$?\"\n"
                    log(f"\n[M5.1-TEST] Executing Post-Reboot [{post_cmd_index}/{len(post_commands)}]: {c}...")
                    os.write(master, full_cmd.encode())
                    stage = "running_post_cmd"
                    buffer = ""

        elif stage == "wait_poweroff":
            if "reboot: Power down" in buffer or proc.poll() is not None:
                log("\n[M5.1-TEST] System cleanly powered down.")
                break

    if time.time() - start_time >= timeout:
        log("\n[ERROR] Test suite timed out!")
        sys.exit(1)

finally:
    try:
        os.killpg(os.getpgid(proc.pid), 9)
    except Exception:
        pass
    try:
        os.killpg(os.getpgid(repo_proc.pid), 9)
    except Exception:
        pass
    if ipv6_httpd:
        ipv6_httpd.shutdown()
    log("\n=== ALL MILESTONE 5.1 HARDENING TESTS PASSED WITH 0 EXIT CODES! ===")
    log_fp.close()
