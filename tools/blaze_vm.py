#!/usr/bin/env python3
# ==============================================================================
# Blaze Universe — Honest QEMU serial test harness
#
# Boots a disk image in a throw-away snapshot, logs in over the serial console,
# runs commands one by one and records their real output and exit status.
# Any timeout, early QEMU exit or unexpected status is a FAILURE — never a pass.
#
# Usage:
#   tools/blaze_vm.py run  -c "systemctl --failed" -c "lynis audit system -Q"
#   tools/blaze_vm.py run  --script checks.txt --json out.json
#   tools/blaze_vm.py boot-log            # only boot, dump serial log
# ==============================================================================
import argparse
import json
import os
import re
import select
import subprocess
import sys
import time
import uuid

BLAZE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_DISK = os.path.join(BLAZE_ROOT, "build", "blaze-disk.raw")
DEFAULT_KERNEL = os.path.join(BLAZE_ROOT, "build", "rootfs", "boot", "vmlinuz-blaze-7.2.9")
DEFAULT_INITRD = os.path.join(BLAZE_ROOT, "build", "rootfs", "boot", "initramfs-blaze-7.2.9.img")
ROOT_PARTUUID = "44444444-4444-4444-4444-444444444444"
ANSI = re.compile(r"\x1b\[[0-9;?!]*[a-zA-Z]|\x1b\][^\x07\x1b]*(\x07|\x1b\\)|\x1bP[^\x1b]*\x1b\\|\x1b[78c]|\r")


class VMError(RuntimeError):
    pass


class BlazeVM:
    def __init__(self, disk, kernel, initrd, memory, cmdline_extra, log_path, verbose):
        self.log_fp = open(log_path, "w", encoding="utf-8", errors="replace")
        self.verbose = verbose
        self.buf = ""
        append = f"root=PARTUUID={ROOT_PARTUUID} rw console=ttyS0,115200 lockdown=integrity {cmdline_extra}".strip()
        cmd = ["qemu-system-x86_64", "-m", str(memory), "-smp", "4",
               "-drive", f"file={disk},format=raw,if=virtio,snapshot=on",
               "-kernel", kernel, "-initrd", initrd, "-append", append,
               "-display", "none", "-vga", "none", "-monitor", "none",
               "-serial", "stdio", "-no-reboot",
               "-nic", "user,model=virtio-net-pci"]
        if os.access("/dev/kvm", os.R_OK | os.W_OK):
            cmd[1:1] = ["-enable-kvm", "-cpu", "host"]
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, bufsize=0)

    # ---------------------------------------------------------------- I/O
    def _pump(self, timeout):
        r, _, _ = select.select([self.proc.stdout], [], [], timeout)
        if not r:
            return
        data = os.read(self.proc.stdout.fileno(), 65536)
        if not data:
            raise VMError(f"QEMU exited unexpectedly (code {self.proc.poll()})")
        text = data.decode("utf-8", errors="replace")
        self.log_fp.write(text)
        self.log_fp.flush()
        if self.verbose:
            sys.stdout.write(text)
            sys.stdout.flush()
        self.buf += ANSI.sub("", text)

    def expect(self, pattern, timeout):
        rx = re.compile(pattern)
        deadline = time.time() + timeout
        while time.time() < deadline:
            m = rx.search(self.buf)
            if m:
                out = self.buf[:m.start()]
                self.buf = self.buf[m.end():]
                return out, m
            if self.proc.poll() is not None:
                raise VMError(f"QEMU exited (code {self.proc.returncode}) while waiting for {pattern!r}")
            self._pump(0.5)
        raise VMError(f"Timed out after {timeout}s waiting for {pattern!r}")

    def send(self, text):
        self.proc.stdin.write(text.encode())
        self.proc.stdin.flush()

    # ----------------------------------------------------------- session
    def settle(self, quiet=3.0, limit=30):
        """Drain output until the console has been quiet for `quiet` seconds."""
        end = time.time() + limit
        last = len(self.buf)
        quiet_since = time.time()
        while time.time() < end:
            self._pump(0.3)
            if len(self.buf) != last:
                last, quiet_since = len(self.buf), time.time()
            elif time.time() - quiet_since >= quiet:
                return

    def login(self, user, password, timeout):
        # Either a getty login prompt or (dev images) an autologin shell prompt.
        deadline = time.time() + timeout
        while True:
            rem = min(15.0, max(1.0, deadline - time.time()))
            try:
                self.expect(r"login: |[#$] ", rem)
                break
            except VMError:
                if time.time() >= deadline:
                    raise
                self.send("\n")
        for _ in range(5):
            self.settle()
            self.buf = ""
            self.send("\n")
            _, m = self.expect(r"login: $|[#$] $", 15)
            if "login" not in m.group(0):
                break
            self.send(user + "\n")
            _, m = self.expect(r"Password: ?$|Parola: ?$|[#$] $|login: $", 20)
            if "login" in m.group(0):
                continue
            if "#" not in m.group(0) and "$" not in m.group(0):
                self.send(password + "\n")
                _, m = self.expect(r"[#$] $|login: $", 20)
                if "login" in m.group(0):
                    raise VMError("login rejected (wrong password?)")
            break
        self.settle(quiet=1.5)
        # Replace the interactive prompt with a unique, unambiguous marker.
        self.marker = "BLZ" + uuid.uuid4().hex[:8]
        # Split the marker with '' so the echoed command line can never match it.
        split = self.marker[:3] + "''" + self.marker[3:]
        self.send(f"unset PROMPT_COMMAND; export TERM=dumb; stty -echo cols 250; export PS2=''; export PS1='{split}> '\n")
        self.expect(re.escape(self.marker) + "> ", 30)

    def run(self, command, timeout):
        tag = uuid.uuid4().hex[:10]
        self.send(f"( {command}\n) 2>&1; echo __RC_{tag}=$?\n")
        out, m = self.expect(rf"__RC_{tag}=(\d+)", timeout)
        self.expect(re.escape(self.marker) + "> ", 10)
        return int(m.group(1)), out.strip("\n")

    def poweroff(self):
        try:
            self.send("systemctl poweroff -i\n")
            self.proc.wait(timeout=30)
        except Exception:
            self.proc.kill()
        self.log_fp.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["run", "boot-log"])
    ap.add_argument("-c", "--command", action="append", default=[])
    ap.add_argument("--script", help="file with one command per line ('#' comments)")
    ap.add_argument("--disk", default=DEFAULT_DISK)
    ap.add_argument("--kernel", default=DEFAULT_KERNEL)
    ap.add_argument("--initrd", default=DEFAULT_INITRD)
    ap.add_argument("--memory", type=int, default=2048)
    ap.add_argument("--append", default="", help="extra kernel cmdline")
    ap.add_argument("--user", default="root")
    ap.add_argument("--password", default=os.environ.get("BLAZE_VM_PASSWORD", "blaze"))
    ap.add_argument("--boot-timeout", type=int, default=120)
    ap.add_argument("--cmd-timeout", type=int, default=300)
    ap.add_argument("--allow-fail", action="store_true", help="do not stop on non-zero exit")
    ap.add_argument("--log", default="/tmp/blaze_vm_serial.log")
    ap.add_argument("--json")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()

    commands = list(a.command)
    if a.script:
        with open(a.script) as f:
            commands += [l.rstrip("\n") for l in f if l.strip() and not l.lstrip().startswith("#")]

    vm = BlazeVM(a.disk, a.kernel, a.initrd, a.memory, a.append, a.log, a.verbose)
    results, ok = [], True
    try:
        if a.mode == "boot-log":
            vm.expect(r"login: ", a.boot_timeout)
            print(f"[PASS] reached login prompt; serial log: {a.log}")
        else:
            vm.login(a.user, a.password, a.boot_timeout)
            for c in commands:
                rc, out = vm.run(c, a.cmd_timeout)
                results.append({"command": c, "rc": rc, "output": out})
                status = "PASS" if rc == 0 else "FAIL"
                print(f"\n===== [{status} rc={rc}] {c}\n{out}")
                if rc != 0:
                    ok = False
                    if not a.allow_fail:
                        break
    except VMError as e:
        ok = False
        print(f"\n[HARNESS FAILURE] {e}\nSerial log: {a.log}", file=sys.stderr)
    finally:
        vm.poweroff()
    if a.json:
        with open(a.json, "w") as f:
            json.dump({"ok": ok, "results": results}, f, indent=2, ensure_ascii=False)
    print(f"\n=== RESULT: {'PASS' if ok else 'FAIL'} ({len(results)}/{len(commands)} commands executed) ===")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
