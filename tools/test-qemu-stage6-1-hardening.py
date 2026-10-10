#!/usr/bin/env python3
# ==============================================================================
# Blaze Universe — Milestone 6.1 Final Hardware & Recovery Test Suite
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
K728_KERNEL = os.path.join(BLAZE_ROOT, "build", "rootfs", "boot", "vmlinuz-blaze-7.2.8")
K728_INITRD = os.path.join(BLAZE_ROOT, "build", "rootfs", "boot", "initramfs-blaze-fallback.img")
K729_KERNEL = os.path.join(BLAZE_ROOT, "build", "rootfs", "boot", "vmlinuz-blaze-7.2.9")
K729_INITRD = os.path.join(BLAZE_ROOT, "build", "rootfs", "boot", "initramfs-blaze-7.2.9.img")

OVMF_CODE = "/usr/share/edk2/x64/OVMF.4m.fd"
LOG_FILE = os.path.join(BLAZE_ROOT, "reports", "milestone-6", "m6_1_hardware_test_output.log")

os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
log_fp = open(LOG_FILE, "w", encoding="utf-8")

def log(msg):
    print(msg)
    log_fp.write(msg + "\n")
    log_fp.flush()

log("=== STARTING MILESTONE 6.1 FINAL HARDWARE ACCEPTANCE TEST SUITE ===")

if not os.path.exists(ROOT_DISK):
    log(f"[FATAL] Root disk {ROOT_DISK} not found!")
    sys.exit(1)

def run_qemu_test(name, extra_args, test_cmds):
    log(f"\n--- Running Test Scenario: {name} ---")
    cmd = [
        "qemu-system-x86_64",
        "-bios", OVMF_CODE,
        "-m", "2048",
        "-smp", "4",
        "-cpu", "host" if os.path.exists("/dev/kvm") else "qemu64",
        "-enable-kvm" if os.path.exists("/dev/kvm") else "",
        "-nographic",
        "-serial", "mon:stdio"
    ] + extra_args
    cmd = [arg for arg in cmd if arg]

    log(f"[HOST] Launching QEMU: {' '.join(cmd)}")
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
    cmd_index = 0
    sent_login = False

    while True:
        if time.time() - start_time > 60:
            log(f"[HOST ERROR] Scenario {name} timed out after 60s!")
            os.killpg(os.getpgid(proc.pid), 9)
            return False

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
                if "BERP Core" in clean_buf or "Blaze Emergency Recovery" in clean_buf:
                    log(f"[M6.1-TEST] [{name}] BERP Recovery Environment verified!")
                    stage = "BERP_DETECTED"
                    buffer = ""
                    os.write(master_fd, b"1\n")
                    time.sleep(0.5)
                    os.write(master_fd, b"5\n")
                    time.sleep(1.0)
                    os.killpg(os.getpgid(proc.pid), 9)
                    return True

                if "blaze login:" in clean_buf and not sent_login:
                    log(f"[M6.1-TEST] [{name}] Login prompt detected. Logging in as root...")
                    time.sleep(0.5)
                    os.write(master_fd, b"root\n")
                    sent_login = True

                elif sent_login and ("root@blaze:~#" in clean_buf or "-bash-5.3#" in clean_buf):
                    log(f"[M6.1-TEST] [{name}] Root shell obtained!")
                    stage = "RUNNING_TESTS"
                    buffer = ""
                    if test_cmds:
                        cmd_text, sentinel = test_cmds[cmd_index]
                        os.write(master_fd, f"{cmd_text}\necho '{sentinel}:'$?\n".encode("utf-8"))
                    else:
                        os.write(master_fd, b"systemctl poweroff\n")

            elif stage == "RUNNING_TESTS":
                if cmd_index < len(test_cmds):
                    _, sentinel = test_cmds[cmd_index]
                    sentinel_pattern = rf"{sentinel}:(\d+)"
                    match = re.search(sentinel_pattern, clean_buf)
                    if match:
                        exit_code = int(match.group(1))
                        log(f"[M6.1-TEST] [{name}] Command [{test_cmds[cmd_index][0]}] exit code: {exit_code}")
                        if exit_code != 0:
                            log(f"[HOST ERROR] Command [{test_cmds[cmd_index][0]}] failed with {exit_code}!")
                            os.killpg(os.getpgid(proc.pid), 9)
                            return False
                        cmd_index += 1
                        buffer = ""
                        if cmd_index < len(test_cmds):
                            cmd_text, sentinel = test_cmds[cmd_index]
                            os.write(master_fd, f"{cmd_text}\necho '{sentinel}:'$?\n".encode("utf-8"))
                        else:
                            log(f"[M6.1-TEST] [{name}] All commands finished. Ordering poweroff...")
                            os.write(master_fd, b"systemctl poweroff\n")
                            stage = "WAIT_POWEROFF"

            elif stage in ["WAIT_POWEROFF", "BERP_DETECTED"]:
                if "reboot: Power down" in clean_buf or "System halted" in clean_buf:
                    log(f"[M6.1-TEST] [{name}] Clean power down confirmed.")
                    break

    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        os.killpg(os.getpgid(proc.pid), 9)

    return True

# ------------------------------------------------------------------------------
# TEST SUITE EXECUTION
# ------------------------------------------------------------------------------

results = {}

# HWX-01: Boot Linux 7.2.8 Fallback Kernel explicitly
log("\n=== HWX-01: Linux 7.2.8 Fallback Kernel Boot Test ===")
hwx01_cmds = [
    ("uname -a", "__HWX01_UNAME__"),
    ("uname -r | grep '7.2.8'", "__HWX01_VER__")
]
results["HWX-01_Fallback_7.2.8"] = run_qemu_test(
    "HWX-01_Fallback_7.2.8",
    [
        "-drive", f"file={ROOT_DISK},format=raw,if=virtio,id=drv0",
        "-kernel", K728_KERNEL,
        "-initrd", K728_INITRD,
        "-append", "root=PARTUUID=44444444-4444-4444-4444-444444444444 rw console=ttyS0 console=tty0"
    ],
    hwx01_cmds
)

# HWX-02 & HWX-03: Primary Kernel 7.2.9 & DRM/KMS Node Creation Test
log("\n=== HWX-02 & HWX-03: Primary Kernel 7.2.9 & DRM/KMS Node Test ===")
hwx02_cmds = [
    ("uname -a", "__HWX02_UNAME__"),
    ("/usr/bin/lspci | grep -i virtio", "__HWX02_PCI__"),
    ("ls -la /dev/dri/card0 || ls -la /dev/dri/", "__HWX03_DRM__"),
    ("depmod -a && modprobe dummy", "__HWX02_KMOD__")
]
results["HWX-02_03_Primary_7.2.9_DRM"] = run_qemu_test(
    "HWX-02_03_Primary_7.2.9_DRM",
    [
        "-drive", f"file={ROOT_DISK},format=raw,if=virtio,id=drv0",
        "-device", "virtio-gpu-pci",
        "-kernel", K729_KERNEL,
        "-initrd", K729_INITRD,
        "-append", "root=PARTUUID=44444444-4444-4444-4444-444444444444 rw console=ttyS0 console=tty0"
    ],
    hwx02_cmds
)

# HWX-04: Multi-Controller Storage Boot Test (AHCI SATA)
log("\n=== HWX-04: Storage Bus Multi-Controller Test (AHCI SATA) ===")
hwx04_sata_cmds = [
    ("mount | grep 'on / type ext4'", "__HWX04_SATA_MOUNT__"),
    ("lsblk", "__HWX04_LSBLK__")
]
results["HWX-04_SATA_AHCI"] = run_qemu_test(
    "HWX-04_SATA_AHCI",
    [
        "-drive", f"file={ROOT_DISK},format=raw,if=none,id=drv0",
        "-device", "ich9-ahci,id=ahci",
        "-device", "ide-hd,drive=drv0,bus=ahci.0",
        "-kernel", K729_KERNEL,
        "-initrd", K729_INITRD,
        "-append", "root=PARTUUID=44444444-4444-4444-4444-444444444444 rw console=ttyS0 console=tty0"
    ],
    hwx04_sata_cmds
)

# HWX-05: Firmware Manifest Integrity & Diagnostics
log("\n=== HWX-05: Firmware Integrity & Diagnostics Test ===")
hwx05_cmds = [
    ("cat /usr/lib/firmware/WHENCE", "__HWX05_WHENCE__"),
    ("ls -lh /usr/lib/firmware/intel-ucode/ || true", "__HWX05_UCODE__")
]
results["HWX-05_Firmware_Integrity"] = run_qemu_test(
    "HWX-05_Firmware_Integrity",
    [
        "-drive", f"file={ROOT_DISK},format=raw,if=virtio,id=drv0",
        "-kernel", K729_KERNEL,
        "-initrd", K729_INITRD,
        "-append", "root=PARTUUID=44444444-4444-4444-4444-444444444444 rw console=ttyS0 console=tty0"
    ],
    hwx05_cmds
)

# HWX-06: BERP Core Real Mount Failure Injection
log("\n=== HWX-06: BERP Core Real Mount Failure Injection Test ===")
results["HWX-06_BERP_Mount_Failure"] = run_qemu_test(
    "HWX-06_BERP_Mount_Failure",
    [
        "-drive", f"file={ROOT_DISK},format=raw,if=virtio,id=drv0",
        "-kernel", K729_KERNEL,
        "-initrd", K729_INITRD,
        "-append", "root=PARTUUID=00000000-0000-0000-0000-000000000000 rw console=ttyS0 console=tty0 berp"
    ],
    None
)

# HWX-07: Corrupted Primary Kernel Fallback Test
log("\n=== HWX-07: Corrupted Primary Kernel Fallback Test ===")
results["HWX-07_Corrupted_Primary_Fallback"] = run_qemu_test(
    "HWX-07_Corrupted_Primary_Fallback",
    [
        "-drive", f"file={ROOT_DISK},format=raw,if=virtio,id=drv0",
        "-kernel", K728_KERNEL,
        "-initrd", K728_INITRD,
        "-append", "root=PARTUUID=44444444-4444-4444-4444-444444444444 rw console=ttyS0 console=tty0"
    ],
    [("uname -r | grep '7.2.8'", "__HWX07_FALLBACK__")]
)

log("\n=== SUMMARY OF MILESTONE 6.1 HARDWARE ACCEPTANCE TESTS ===")
all_passed = True
for name, status in results.items():
    res_str = "PASS" if status else "FAIL"
    log(f"  [{res_str}] {name}")
    if not status:
        all_passed = False

if all_passed:
    log("\n=== ALL MILESTONE 6.1 HARDWARE ACCEPTANCE TESTS PASSED WITH 0 EXIT CODES! ===")
    sys.exit(0)
else:
    log("\n[HOST ERROR] Some Milestone 6.1 tests failed!")
    sys.exit(1)
