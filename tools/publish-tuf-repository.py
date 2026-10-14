#!/usr/bin/env python3
"""BlazeOS deterministic two-step TUF repository publisher.

Offline step owns root/targets keys and emits a signed transfer bundle.
Online step owns only snapshot/timestamp keys and atomically publishes a channel.
No private key is ever written to the published tree.
"""

import argparse
import datetime as dt
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import tarfile
import tempfile

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519


TUF_SPEC_VERSION = "1.0.37"
CHANNELS = ("stable", "staging")
STABLE_DENY = (
    "conflict-*",
    "corrupt-*",
    "cycle-*",
    "portadora-broken-*",
)


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def pretty_json(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode()


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def file_info(path):
    data = path.read_bytes()
    return {"length": len(data), "hashes": {"sha256": sha256_bytes(data)}}


def expiry(epoch, days):
    value = dt.datetime.fromtimestamp(epoch, tz=dt.timezone.utc) + dt.timedelta(days=days)
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def public_descriptor(public_hex):
    return {"keytype": "ed25519", "scheme": "ed25519", "keyval": public_hex}


def key_id(public_hex):
    return sha256_bytes(canonical_json(public_descriptor(public_hex)))


def generate_key(private_path):
    private = ed25519.Ed25519PrivateKey.generate()
    private_raw = private.private_bytes(
        serialization.Encoding.Raw,
        serialization.PrivateFormat.Raw,
        serialization.NoEncryption(),
    )
    public_raw = private.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    private_path.parent.mkdir(parents=True, exist_ok=True)
    private_path.write_text(private_raw.hex() + "\n")
    os.chmod(private_path, stat.S_IRUSR | stat.S_IWUSR)
    public_hex = public_raw.hex()
    return {"keyid": key_id(public_hex), "public": public_hex}


def load_private(path):
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        raise SystemExit(f"private key permissions must be 0600: {path} ({mode:o})")
    return ed25519.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(path.read_text().strip()))


def checked_private(path, expected_public):
    private = load_private(path)
    actual = private.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    ).hex()
    if actual != expected_public:
        raise SystemExit(f"private key does not match recorded public key: {path}")
    return private


def sign_envelope(signed, keyid, private):
    signature = private.sign(canonical_json(signed)).hex()
    return {"signatures": [{"keyid": keyid, "sig": signature}], "signed": signed}


def extract_manifest(package):
    with tarfile.open(package, "r") as archive:
        member = archive.getmember("manifest.toml")
        extracted = archive.extractfile(member)
        if extracted is None:
            raise ValueError(f"missing manifest.toml: {package}")
        import tomllib
        return tomllib.loads(extracted.read().decode())


def package_target(package):
    manifest = extract_manifest(package)
    pkg = manifest.get("package", {})
    deps = manifest.get("dependencies", {})
    info = file_info(package)
    info["custom"] = {
        "name": pkg.get("name", package.name.split("-")[0]),
        "version": str(pkg.get("version", "1.0")),
        "release": int(pkg.get("release", 1)),
        "architecture": pkg.get("architecture", "x86_64"),
        "summary": pkg.get("summary", ""),
        "requires": deps.get("requires", []),
        "provides": deps.get("provides", []),
        "conflicts": deps.get("conflicts", []),
        "replaces": deps.get("replaces", []),
    }
    return info


def ensure_channel(channel):
    if channel not in CHANNELS:
        raise SystemExit(f"unsupported channel: {channel}")


def keygen(offline_dir, online_dir, force=False):
    offline_dir = offline_dir.resolve()
    online_dir = online_dir.resolve()
    if (offline_dir.exists() or online_dir.exists()) and not force:
        raise SystemExit("key directories already exist; refusing to overwrite (use --force only for disposable tests)")
    if force:
        shutil.rmtree(offline_dir, ignore_errors=True)
        shutil.rmtree(online_dir, ignore_errors=True)

    public = {"spec_version": TUF_SPEC_VERSION, "channels": {}}
    for channel in CHANNELS:
        channel_public = {}
        for role in ("root", "targets"):
            channel_public[role] = generate_key(offline_dir / "private" / channel / f"{role}.key")
        for role in ("snapshot", "timestamp"):
            channel_public[role] = generate_key(online_dir / "private" / channel / f"{role}.key")
        public["channels"][channel] = channel_public

    (offline_dir / "public-keys.json").write_bytes(pretty_json(public))
    (online_dir / "public-keys.json").write_bytes(pretty_json(public))
    os.chmod(offline_dir, 0o700)
    os.chmod(online_dir, 0o700)
    for private_dir in (offline_dir / "private", online_dir / "private"):
        os.chmod(private_dir, 0o700)
        for channel_dir in private_dir.iterdir():
            os.chmod(channel_dir, 0o700)
    print(f"[keygen] offline root/targets keys: {offline_dir}")
    print(f"[keygen] online snapshot/timestamp keys: {online_dir}")


def offline_sign(channel, packages_dir, offline_dir, bundle_dir, epoch, version):
    ensure_channel(channel)
    packages_dir = packages_dir.resolve()
    offline_dir = offline_dir.resolve()
    bundle_dir = bundle_dir.resolve()
    public = json.loads((offline_dir / "public-keys.json").read_text())
    roles = public["channels"][channel]

    if bundle_dir.exists():
        shutil.rmtree(bundle_dir)
    (bundle_dir / "metadata").mkdir(parents=True)
    (bundle_dir / "packages").mkdir()

    targets = {}
    excluded = []
    for package in sorted(packages_dir.glob("*.blz"), key=lambda p: p.name):
        denied = channel == "stable" and any(fnmatch.fnmatch(package.name, rule) for rule in STABLE_DENY)
        if denied:
            excluded.append(package.name)
            continue
        destination = bundle_dir / "packages" / package.name
        shutil.copyfile(package, destination)
        os.utime(destination, (epoch, epoch))
        targets[package.name] = package_target(destination)

    if not targets:
        raise SystemExit("refusing to publish an empty channel")

    root_signed = {
        "_type": "root", "spec_version": TUF_SPEC_VERSION, "version": version,
        "expires": expiry(epoch, 365), "consistent_snapshot": False,
        "keys": {
            roles[role]["keyid"]: public_descriptor(roles[role]["public"])
            for role in ("root", "targets", "snapshot", "timestamp")
        },
        "roles": {
            role: {"keyids": [roles[role]["keyid"]], "threshold": 1}
            for role in ("root", "targets", "snapshot", "timestamp")
        },
    }
    targets_signed = {
        "_type": "targets", "spec_version": TUF_SPEC_VERSION, "version": version,
        "expires": expiry(epoch, 30), "targets": targets,
    }
    root = sign_envelope(root_signed, roles["root"]["keyid"], checked_private(offline_dir / "private" / channel / "root.key", roles["root"]["public"]))
    target_meta = sign_envelope(targets_signed, roles["targets"]["keyid"], checked_private(offline_dir / "private" / channel / "targets.key", roles["targets"]["public"]))
    (bundle_dir / "metadata" / "root.json").write_bytes(pretty_json(root))
    (bundle_dir / "metadata" / f"{version}.root.json").write_bytes(pretty_json(root))
    (bundle_dir / "metadata" / "targets.json").write_bytes(pretty_json(target_meta))

    transfer = {
        "format": 1, "channel": channel, "spec_version": TUF_SPEC_VERSION,
        "source_date_epoch": epoch, "version": version,
        "package_count": len(targets), "excluded": excluded,
    }
    transfer["files"] = manifest_files(bundle_dir)
    (bundle_dir / "offline-transfer.json").write_bytes(pretty_json(transfer))
    normalize_tree(bundle_dir, epoch)
    print(f"[offline-sign] {channel}: {len(targets)} packages, {len(excluded)} excluded")


def manifest_files(root):
    result = {}
    for path in sorted((p for p in root.rglob("*") if p.is_file()), key=lambda p: p.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        if relative in ("offline-transfer.json", "release-manifest.json", "SHA256SUMS"):
            continue
        result[relative] = file_info(path)
    return result


def normalize_tree(root, epoch):
    for path in sorted(root.rglob("*"), reverse=True):
        if path.is_file():
            os.chmod(path, 0o644)
        os.utime(path, (epoch, epoch), follow_symlinks=False)
    os.utime(root, (epoch, epoch))


def verify_transfer(bundle_dir, transfer):
    if transfer.get("format") != 1 or transfer.get("spec_version") != TUF_SPEC_VERSION:
        raise SystemExit("unsupported or stale offline transfer format")
    actual = manifest_files(bundle_dir)
    if actual != transfer.get("files"):
        raise SystemExit("offline transfer integrity check failed")


def fsync_tree(root):
    for path in root.rglob("*"):
        if path.is_file():
            with path.open("rb") as handle:
                os.fsync(handle.fileno())
    for path in sorted((p for p in root.rglob("*") if p.is_dir()), reverse=True):
        fd = os.open(path, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def online_publish(bundle_dir, online_dir, output_root):
    bundle_dir = bundle_dir.resolve()
    online_dir = online_dir.resolve()
    output_root = output_root.resolve()
    transfer = json.loads((bundle_dir / "offline-transfer.json").read_text())
    channel = transfer["channel"]
    ensure_channel(channel)
    epoch = int(transfer["source_date_epoch"])
    version = int(transfer["version"])
    verify_transfer(bundle_dir, transfer)

    public = json.loads((online_dir / "public-keys.json").read_text())
    roles = public["channels"][channel]
    target = output_root / channel
    output_root.mkdir(parents=True, exist_ok=True)
    previous_version = None
    if (target / "release-manifest.json").is_file():
        previous_version = int(json.loads((target / "release-manifest.json").read_text())["version"])
        if version < previous_version:
            raise SystemExit(f"repository rollback refused: version {version} < published {previous_version}")
    staging = Path(tempfile.mkdtemp(prefix=f".{channel}.publish-", dir=output_root))
    backup = output_root / f".{channel}.previous"
    try:
        shutil.copytree(bundle_dir / "metadata", staging / "metadata")
        shutil.copytree(bundle_dir / "packages", staging / "packages")
        targets_info = file_info(staging / "metadata" / "targets.json")
        snapshot_signed = {
            "_type": "snapshot", "spec_version": TUF_SPEC_VERSION, "version": version,
            "expires": expiry(epoch, 30), "meta": {"targets.json": {"version": version, **targets_info}},
        }
        snapshot_private = checked_private(online_dir / "private" / channel / "snapshot.key", roles["snapshot"]["public"])
        snapshot = sign_envelope(snapshot_signed, roles["snapshot"]["keyid"], snapshot_private)
        (staging / "metadata" / "snapshot.json").write_bytes(pretty_json(snapshot))
        snapshot_info = file_info(staging / "metadata" / "snapshot.json")
        timestamp_signed = {
            "_type": "timestamp", "spec_version": TUF_SPEC_VERSION, "version": version,
            "expires": expiry(epoch, 7), "meta": {"snapshot.json": {"version": version, **snapshot_info}},
        }
        timestamp = sign_envelope(timestamp_signed, roles["timestamp"]["keyid"], checked_private(online_dir / "private" / channel / "timestamp.key", roles["timestamp"]["public"]))
        (staging / "metadata" / "timestamp.json").write_bytes(pretty_json(timestamp))

        release = {
            "format": 1, "channel": channel, "spec_version": TUF_SPEC_VERSION,
            "source_date_epoch": epoch, "version": version,
            "files": manifest_files(staging),
        }
        release_bytes = pretty_json(release)
        (staging / "release-manifest.json").write_bytes(release_bytes)
        release_signature = {
            "keyid": roles["snapshot"]["keyid"],
            "sig": snapshot_private.sign(release_bytes).hex(),
        }
        (staging / "release-manifest.sig").write_bytes(pretty_json(release_signature))
        checksum_lines = [f"{info['hashes']['sha256']}  {name}" for name, info in release["files"].items()]
        checksum_lines.append(f"{sha256_bytes(release_bytes)}  release-manifest.json")
        checksum_lines.append(f"{sha256_bytes((staging / 'release-manifest.sig').read_bytes())}  release-manifest.sig")
        (staging / "SHA256SUMS").write_text("\n".join(checksum_lines) + "\n")
        normalize_tree(staging, epoch)
        fsync_tree(staging)

        if previous_version == version and target.exists():
            if manifest_files(staging) != manifest_files(target):
                raise SystemExit(f"non-idempotent republish refused at version {version}")

        shutil.rmtree(backup, ignore_errors=True)
        if target.exists():
            os.replace(target, backup)
        try:
            os.replace(staging, target)
        except Exception:
            if backup.exists():
                os.replace(backup, target)
            raise
        shutil.rmtree(backup, ignore_errors=True)
    finally:
        if staging.exists():
            shutil.rmtree(staging)

    leaked = list(target.rglob("*.key")) + list(target.rglob("private*"))
    if leaked:
        raise SystemExit(f"private material leaked into published tree: {leaked}")
    print(f"[online-publish] atomically published {channel} at {target}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    keys = sub.add_parser("keygen")
    keys.add_argument("--offline-dir", required=True, type=Path)
    keys.add_argument("--online-dir", required=True, type=Path)
    keys.add_argument("--force", action="store_true")
    off = sub.add_parser("offline-sign")
    off.add_argument("--channel", choices=CHANNELS, required=True)
    off.add_argument("--packages-dir", required=True, type=Path)
    off.add_argument("--offline-dir", required=True, type=Path)
    off.add_argument("--bundle-dir", required=True, type=Path)
    off.add_argument("--source-date-epoch", required=True, type=int)
    off.add_argument("--version", required=True, type=int)
    pub = sub.add_parser("online-publish")
    pub.add_argument("--bundle-dir", required=True, type=Path)
    pub.add_argument("--online-dir", required=True, type=Path)
    pub.add_argument("--output-root", required=True, type=Path)
    args = parser.parse_args()
    if args.command == "keygen":
        keygen(args.offline_dir, args.online_dir, args.force)
    elif args.command == "offline-sign":
        offline_sign(args.channel, args.packages_dir, args.offline_dir, args.bundle_dir, args.source_date_epoch, args.version)
    else:
        online_publish(args.bundle_dir, args.online_dir, args.output_root)


if __name__ == "__main__":
    main()
