#!/usr/bin/env python3
# ==============================================================================
# Blaze Universe — Security enforcement acceptance test (M7.1, rewritten 2026-11)
#
# The previous version of this script printed "ALL TESTS PASSED" whenever the
# QEMU console closed, even if zero checks had run, and invoked blaze-sentinel
# sub-commands that do not exist. It now delegates to the honest harness
# tools/blaze_vm.py: every check must report exit status 0, and any timeout or
# early VM exit is a failure.
# ==============================================================================
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LOG_DIR = os.path.join(ROOT, "reports", "milestone-7")
os.makedirs(LOG_DIR, exist_ok=True)

cmd = [sys.executable, os.path.join(ROOT, "tools", "blaze_vm.py"), "run",
       "--script", os.path.join(ROOT, "tools", "tests", "security-acceptance.txt"),
       "--allow-fail", "--cmd-timeout", "180",
       "--log", os.path.join(LOG_DIR, "m7_1_enforcement_serial.log"),
       "--json", os.path.join(LOG_DIR, "m7_1_enforcement_results.json")]
with open(os.path.join(LOG_DIR, "m7_1_enforcement_test_output.log"), "w") as out:
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    out.write(p.stdout)
    sys.stdout.write(p.stdout)
sys.exit(p.returncode)
