#!/usr/bin/env python3
"""
M9 Phase B.1.1 — apply corrected package revisions through REAL Portadora transactions.

1. Clone build/rootfs -> build/rootfs-b11 (disposable; baseline untouched)
2. Publish build/b11_pkgs into a TUF repo (build/repo-b11, same signing keys as build/repo)
3. `portadora update` + `portadora upgrade` against the clone (journaled transaction,
   self-upgrade sanity check included)
4. `portadora verify` on the clone, report result honestly

No SQLite record is edited by hand and nothing is copied into the clone outside Portadora,
other than provisioning the test repository's TUF root anchor (trust provisioning, not
package content).
"""
import os, shutil, subprocess, sys, time, signal

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
B = os.path.join(ROOT, "build")
CLONE = os.path.join(B, "rootfs-b11")
REPO = os.path.join(B, "repo-b11")
PKGS = os.path.join(B, "b11_pkgs")
PORT = 8081
PORTADORA = os.path.join(ROOT, "target", "release", "portadora")

def run(cmd, check=True, **kw):
    print("$", cmd if isinstance(cmd, str) else " ".join(cmd), flush=True)
    return subprocess.run(cmd, shell=isinstance(cmd, str), check=check, **kw)

if "--keep-clone" not in sys.argv:
    run(f"rm -rf '{CLONE}'")
    # cp returns non-zero for root-only runtime dirs (/run/systemd/dissect-root); not package content
    run(f"cp -a '{B}/rootfs' '{CLONE}'", check=False)
run(f"rm -rf '{REPO}'")
os.makedirs(f"{REPO}/keys", exist_ok=True)
run(f"cp '{B}/repo/keys/'* '{REPO}/keys/'")
run([sys.executable, f"{ROOT}/tools/repo-server.py", "init", "--repo-dir", REPO, "--pkgs-dir", PKGS])
shutil.copy2(f"{REPO}/metadata/root.json", f"{CLONE}/etc/portadora/trusted/root.json")

server = subprocess.Popen([sys.executable, f"{ROOT}/tools/repo-server.py", "serve",
                           "--repo-dir", REPO, "--port", str(PORT)],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
time.sleep(2)
env = dict(os.environ, BLAZE_REPO_URL=f"http://127.0.0.1:{PORT}")
try:
    run([PORTADORA, "--root", CLONE, "update"], env=env)
    run([PORTADORA, "--root", CLONE, "-v", "upgrade"], env=env)
finally:
    os.killpg(os.getpgid(server.pid), signal.SIGTERM)

rc = run([f"{CLONE}/usr/bin/portadora", "--root", CLONE, "-v", "verify"], check=False).returncode
print(f"[B1.1] clone portadora verify exit code: {rc}")
sys.exit(rc)
