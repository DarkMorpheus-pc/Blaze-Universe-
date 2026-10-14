#!/usr/bin/env python3
"""Milestone 10 Phase C.2 deterministic publication acceptance tests."""

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from cryptography.hazmat.primitives.asymmetric import ed25519


ROOT = Path(__file__).resolve().parents[1]
PUBLISHER = ROOT / "tools" / "publish-tuf-repository.py"
PACKAGES = ROOT / "build" / "packages"
EPOCH = "1791936000"  # 2026-10-14T00:00:00Z


def run(*args, ok=True):
    result = subprocess.run([sys.executable, str(PUBLISHER), *map(str, args)], text=True, capture_output=True)
    if ok and result.returncode:
        raise AssertionError(f"command failed ({result.returncode}):\n{result.stdout}\n{result.stderr}")
    if not ok and result.returncode == 0:
        raise AssertionError("command unexpectedly succeeded")
    return result


def digest_tree(root):
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest.update(path.relative_to(root).as_posix().encode() + b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def main():
    required = [
        PACKAGES / "nano-8.1-1.x86_64.blz",
        PACKAGES / "portadora-broken-format-0.3.0-1.x86_64.blz",
    ]
    if not all(path.is_file() for path in required):
        raise SystemExit("required built packages are missing")

    with tempfile.TemporaryDirectory(prefix="blaze-c2-") as temp:
        work = Path(temp)
        package_fixture = work / "packages"
        package_fixture.mkdir()
        for package in required:
            shutil.copyfile(package, package_fixture / package.name)

        offline = work / "offline"
        online = work / "online"
        run("keygen", "--offline-dir", offline, "--online-dir", online)

        public = json.loads((offline / "public-keys.json").read_text())
        assert public["spec_version"] == "1.0.37"
        assert public["channels"]["stable"]["root"]["keyid"] != public["channels"]["staging"]["root"]["keyid"]
        assert not (online / "private" / "stable" / "root.key").exists()
        assert not (online / "private" / "stable" / "targets.key").exists()
        assert not (offline / "private" / "stable" / "timestamp.key").exists()

        stable_a = work / "stable-a"
        stable_b = work / "stable-b"
        staging = work / "staging"
        common = ("--packages-dir", package_fixture, "--offline-dir", offline,
                  "--source-date-epoch", EPOCH, "--version", "1")
        run("offline-sign", "--channel", "stable", "--bundle-dir", stable_a, *common)
        run("offline-sign", "--channel", "stable", "--bundle-dir", stable_b, *common)
        run("offline-sign", "--channel", "staging", "--bundle-dir", staging, *common)
        assert digest_tree(stable_a) == digest_tree(stable_b), "offline output is not deterministic"
        stable_targets = json.loads((stable_a / "metadata" / "targets.json").read_text())["signed"]["targets"]
        staging_targets = json.loads((staging / "metadata" / "targets.json").read_text())["signed"]["targets"]
        assert "nano-8.1-1.x86_64.blz" in stable_targets
        assert "portadora-broken-format-0.3.0-1.x86_64.blz" not in stable_targets
        assert "portadora-broken-format-0.3.0-1.x86_64.blz" in staging_targets

        output_a = work / "publish-a"
        output_b = work / "publish-b"
        run("online-publish", "--bundle-dir", stable_a, "--online-dir", online, "--output-root", output_a)
        run("online-publish", "--bundle-dir", stable_b, "--online-dir", online, "--output-root", output_b)
        assert digest_tree(output_a / "stable") == digest_tree(output_b / "stable"), "online output is not deterministic"
        assert not list((output_a / "stable").rglob("*.key"))
        assert not list((output_a / "stable").rglob("private*"))
        release = json.loads((output_a / "stable" / "release-manifest.json").read_text())
        assert release["channel"] == "stable" and release["spec_version"] == "1.0.37"
        signature = json.loads((output_a / "stable" / "release-manifest.sig").read_text())
        snapshot_public = bytes.fromhex(public["channels"]["stable"]["snapshot"]["public"])
        ed25519.Ed25519PublicKey.from_public_bytes(snapshot_public).verify(
            bytes.fromhex(signature["sig"]), (output_a / "stable" / "release-manifest.json").read_bytes()
        )

        preserved = digest_tree(output_a / "stable")
        with (stable_a / "packages" / "nano-8.1-1.x86_64.blz").open("ab") as handle:
            handle.write(b"tamper")
        failed = run("online-publish", "--bundle-dir", stable_a, "--online-dir", online,
                     "--output-root", output_a, ok=False)
        assert "integrity check failed" in (failed.stdout + failed.stderr)
        assert digest_tree(output_a / "stable") == preserved, "failed publication changed live channel"

        rollback_bundle = work / "rollback"
        run("offline-sign", "--channel", "stable", "--bundle-dir", rollback_bundle,
            "--packages-dir", package_fixture, "--offline-dir", offline,
            "--source-date-epoch", EPOCH, "--version", "0")
        failed = run("online-publish", "--bundle-dir", rollback_bundle, "--online-dir", online,
                     "--output-root", output_a, ok=False)
        assert "rollback refused" in (failed.stdout + failed.stderr)

    print("[M10-C2] PASS: key separation, channel policy, determinism, integrity, atomic rollback")


if __name__ == "__main__":
    main()
