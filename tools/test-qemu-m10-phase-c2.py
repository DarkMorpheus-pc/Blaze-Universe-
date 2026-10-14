#!/usr/bin/env python3
"""Milestone 10 C.2 Live ISO and remote repository acceptance test."""

import atexit
import os
from pathlib import Path
import pty
import re
import select
import signal
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
ISO = ROOT / "build/iso/BlazeOS-Native-m10-phase-c2-x86_64.iso"
OVMF = Path("/usr/share/edk2/x64/OVMF.4m.fd")
LOG = ROOT / "reports/milestone-10/m10_phase_c2_vm_acceptance.log"
proc = None
master = None


def cleanup():
    if proc is not None and proc.poll() is None:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    if master is not None:
        try:
            os.close(master)
        except OSError:
            pass


atexit.register(cleanup)


def emit(text):
    print(text, flush=True)
    log.write(text)
    log.flush()


def read_until(pattern, timeout):
    end = time.monotonic() + timeout
    collected = ""
    while time.monotonic() < end:
        ready, _, _ = select.select([master], [], [], 0.5)
        if ready:
            try:
                chunk = os.read(master, 4096).decode(errors="replace")
            except OSError:
                break
            collected += chunk
            log.write(chunk)
            log.flush()
            clean = re.sub(r"\x1b\[[0-9;?]*[ -/]*[@-~]", "", collected)
            if re.search(pattern, clean, re.MULTILINE):
                return clean
        if proc.poll() is not None:
            break
    raise AssertionError(f"timeout waiting for {pattern!r}; tail={collected[-2000:]!r}")


def send(line):
    os.write(master, (line + "\n").encode())


def check(number, command, expected=None, timeout=60):
    marker = f"__C2_{number}__"
    send(f"{command}; rc=$?; echo {marker}:$rc")
    output = read_until(marker + r":(\d+)", timeout)
    match = re.search(marker + r":(\d+)", output)
    if not match or match.group(1) != "0":
        raise AssertionError(f"command failed: {command}\n{output[-3000:]}")
    if expected and expected not in output:
        raise AssertionError(f"missing {expected!r}: {command}\n{output[-3000:]}")
    emit(f"[PASS] {number}: {command}\n")


if not ISO.is_file() or not OVMF.is_file():
    raise SystemExit(f"missing ISO or OVMF: {ISO}, {OVMF}")

LOG.parent.mkdir(parents=True, exist_ok=True)
log = LOG.open("w")
cmd = [
    "qemu-system-x86_64", "-bios", str(OVMF), "-m", "4096", "-smp", "4",
    "-cdrom", str(ISO), "-boot", "d", "-device", "virtio-vga-gl",
    "-device", "virtio-tablet-pci", "-device", "virtio-keyboard-pci",
    "-netdev", "user,id=net0", "-device", "virtio-net-pci,netdev=net0",
    "-display", "gtk,gl=on", "-serial", "stdio", "-monitor", "none",
]
if os.access("/dev/kvm", os.R_OK | os.W_OK):
    cmd[1:1] = ["-enable-kvm", "-cpu", "host"]

master, slave = pty.openpty()
proc = subprocess.Popen(cmd, stdin=slave, stdout=slave, stderr=slave, close_fds=True, preexec_fn=os.setsid)
os.close(slave)
emit("[M10-C2] QEMU Live ISO boot started\n")

try:
    boot = read_until(r"(login:|blaze@|root@|[#\$] )", 150)
    if "login:" in boot:
        send("root")
        auth = read_until(r"(Password:|[#] )", 20)
        if "Password:" in auth:
            send("root")
            read_until(r"[#] ", 20)

    check("01", "grep -q 'Milestone 10 Phase C.2' /run/live/media/.disk/info")
    check("02", "state=$(systemctl is-system-running --wait); echo SYSTEM_STATE:$state; test \"$state\" = running || { systemctl --failed --no-pager -l; journalctl -b -p err --no-pager -n 60; false; }", "SYSTEM_STATE:running")
    check("03", "portadora --version", "0.2.0")
    check("04", "grep -q '\"spec_version\": \"1.0.37\"' /etc/portadora/trusted/root.json")
    check("05", "portadora update --repo-url http://10.0.2.2:18082", "TUF v1.0.37")
    check("06", "portadora search fastfetch --repo-url http://10.0.2.2:18082", "fastfetch")
    check("07", "portadora search portadora-broken-format --repo-url http://10.0.2.2:18082 | grep -q 'No packages found'")
    check("08", "portadora install niri-session-assets --repo-url http://10.0.2.2:18082")
    check("09", "portadora verify niri-session-assets")
    check("10", "! portadora update --repo-url http://10.0.2.2:18083", "ThresholdNotMet")
    check("11", "test -z \"$(systemctl --failed --no-legend --plain)\"")
    check("12", "found=0; for i in 1 2 3 4 5; do if pgrep -x niri >/dev/null && (pgrep -f noctalia >/dev/null || pgrep -f solar-shell >/dev/null); then found=1; break; fi; sleep 2; done; if [ $found -eq 0 ]; then systemctl status getty@tty1.service --no-pager -l; journalctl -b -u getty@tty1.service --no-pager -n 30; fi; test $found -eq 1", timeout=90)
    send("poweroff -f")
    emit("[M10-C2] PASS: Live ISO, desktop, stable repository, install, integrity and channel isolation\n")
except Exception as error:
    emit(f"[M10-C2] FAIL: {error}\n")
    raise
finally:
    log.close()
