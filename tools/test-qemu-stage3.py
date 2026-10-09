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
timeout = 300

commands_to_run = [
    "uname -a",
    "cat /etc/os-release",
    "systemctl is-system-running",
    "gcc --version",
    "g++ --version",
    # C compilation test
    "cat << 'EOC' > /root/hello.c\n#include <stdio.h>\nint main() { printf(\"HELLO_C_NATIVE_OK\\n\"); return 0; }\nEOC",
    "gcc -O2 /root/hello.c -o /root/hello",
    "/root/hello",
    # C++ compilation test
    "cat << 'EOC' > /root/hello.cpp\n#include <iostream>\n#include <vector>\nint main() { std::vector<int> v={1,2,3}; std::cout << \"HELLO_CXX_NATIVE_OK \" << v.size() << std::endl; return 0; }\nEOC",
    "g++ -O2 /root/hello.cpp -o /root/hello-cpp",
    "/root/hello-cpp",
    # Contamination & ABI audit
    "readelf -l /root/hello | grep interpreter",
    "readelf -d /root/hello | grep -E 'RPATH|RUNPATH' || echo 'AUDIT_RPATH_CLEAN_OK'",
    "readelf -d /root/hello | grep NEEDED",
    "/lib64/ld-linux-x86-64.so.2 --list /root/hello",
    # In-VM Native Package Build test (blaze-builder)
    "mkdir -p /root/packages",
    "blaze-builder /usr/share/blaze/recipes/core/zlib/native-recipe.toml --sources-dir /usr/share/blaze/sources --output-dir /root/packages --work-dir /tmp/build",
    "ls -lh /root/packages/",
    # Install generated package and verify
    "portadora install /root/packages/zlib-1.3.1-1.x86_64.blz",
    "portadora verify",
    # Final reboot check
    "reboot -f",
]
cmd_index = 0
last_cmd_time = 0

print("=== Starting Automated QEMU Milestone 3 In-VM Self-Hosting Test ===")
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
                    print("\n[STAGE3] Detected login prompt. Sending 'root'...")
                    time.sleep(0.5)
                    os.write(master, b"root\n")
                    buffer = ""
                    stage = "logged_in"
                    last_cmd_time = time.time()

        if stage == "wait_relogin" and "blaze login:" in buffer:
            print("\n[STAGE3] REBOOT OK: Second login prompt returned successfully.")
            break

        if stage == "logged_in" and (time.time() - last_cmd_time > 3.0):
            if cmd_index < len(commands_to_run):
                c = commands_to_run[cmd_index]
                print(f"\n[STAGE3] Executing [{cmd_index+1}/{len(commands_to_run)}]: {c[:60]}...")
                os.write(master, (c + "\n").encode())
                cmd_index += 1
                last_cmd_time = time.time()
            else:
                print("\n[STAGE3] All commands dispatched. Waiting for reboot...")
                stage = "wait_relogin"
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
    print("\n=== Test Finished ===")
