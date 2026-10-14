#!/usr/bin/env python3
import argparse
import datetime
import hashlib
import http.server
import json
import os
import shutil
import socketserver
import sys
import tarfile
import tempfile

from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

TUF_SPEC_VERSION = "1.0.36"

def canonical_json(data):
    def sort_value(v):
        if isinstance(v, dict):
            return {k: sort_value(v[k]) for k in sorted(v.keys())}
        elif isinstance(v, list):
            return [sort_value(i) for i in v]
        return v
    sorted_data = sort_value(data)
    return json.dumps(sorted_data, separators=(',', ':'), ensure_ascii=False).encode('utf-8')

def gen_key():
    priv = ed25519.Ed25519PrivateKey.generate()
    pub = priv.public_key()
    pub_bytes = pub.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    priv_bytes = priv.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption()
    )
    return priv, pub_bytes.hex(), priv_bytes.hex()

def sign(priv, data_bytes):
    sig = priv.sign(data_bytes)
    return sig.hex()

def extract_blz_manifest(blz_path):
    with tarfile.open(blz_path, 'r') as tar:
        for member in tar:
            if member.name == 'manifest.toml':
                extracted = tar.extractfile(member)
                if extracted:
                    import tomllib
                    return tomllib.loads(extracted.read().decode('utf-8'))
    return {}

def init_repo(repo_dir, pkgs_dir):
    repo_dir = os.path.abspath(repo_dir)
    os.makedirs(os.path.join(repo_dir, "keys"), exist_ok=True)
    os.makedirs(os.path.join(repo_dir, "metadata"), exist_ok=True)
    os.makedirs(os.path.join(repo_dir, "packages"), exist_ok=True)
    os.makedirs(os.path.join(repo_dir, "metadata-expired"), exist_ok=True)
    os.makedirs(os.path.join(repo_dir, "metadata-rollback"), exist_ok=True)

    priv_path = os.path.join(repo_dir, "keys", "private_keys.json")
    if os.path.exists(priv_path):
        with open(priv_path, "r") as f:
            priv_data = json.load(f)
        root_priv = ed25519.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(priv_data["root"]["priv"]))
        root_pub = priv_data["root"]["pub"]
        root_priv_hex = priv_data["root"]["priv"]
        ts_priv = ed25519.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(priv_data["timestamp"]["priv"]))
        ts_pub = priv_data["timestamp"]["pub"]
        ts_priv_hex = priv_data["timestamp"]["priv"]
        snap_priv = ed25519.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(priv_data["snapshot"]["priv"]))
        snap_pub = priv_data["snapshot"]["pub"]
        snap_priv_hex = priv_data["snapshot"]["priv"]
        tgt_priv = ed25519.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(priv_data["targets"]["priv"]))
        tgt_pub = priv_data["targets"]["pub"]
        tgt_priv_hex = priv_data["targets"]["priv"]
    else:
        root_priv, root_pub, root_priv_hex = gen_key()
        ts_priv, ts_pub, ts_priv_hex = gen_key()
        snap_priv, snap_pub, snap_priv_hex = gen_key()
        tgt_priv, tgt_pub, tgt_priv_hex = gen_key()

        # Save keys
        keys_info = {
            "root": {"pub": root_pub, "keyid": "key-root"},
            "timestamp": {"pub": ts_pub, "keyid": "key-ts"},
            "snapshot": {"pub": snap_pub, "keyid": "key-snap"},
            "targets": {"pub": tgt_pub, "keyid": "key-tgt"},
        }
        with open(os.path.join(repo_dir, "keys", "keys.json"), "w") as f:
            json.dump(keys_info, f, indent=2)

        priv_keys_info = {
            "root": {"priv": root_priv_hex, "pub": root_pub, "keyid": "key-root"},
            "timestamp": {"priv": ts_priv_hex, "pub": ts_pub, "keyid": "key-ts"},
            "snapshot": {"priv": snap_priv_hex, "pub": snap_pub, "keyid": "key-snap"},
            "targets": {"priv": tgt_priv_hex, "pub": tgt_pub, "keyid": "key-tgt"},
        }
        with open(priv_path, "w") as f:
            json.dump(priv_keys_info, f, indent=2)
    os.chmod(priv_path, 0o600)

    # Copy selected packages
    targets_dict = {}
    for fname in sorted(os.listdir(pkgs_dir)):
        if fname.endswith(".blz"):
            src_pkg = os.path.join(pkgs_dir, fname)
            dst_pkg = os.path.join(repo_dir, "packages", fname)
            shutil.copy2(src_pkg, dst_pkg)

            with open(src_pkg, "rb") as f:
                content = f.read()
                h = hashlib.sha256(content).hexdigest()
                size = len(content)

            manifest = extract_blz_manifest(src_pkg)
            pkg_meta = manifest.get("package", {})
            deps_meta = manifest.get("dependencies", {})

            targets_dict[fname] = {
                "length": size,
                "hashes": {"sha256": h},
                "custom": {
                    "name": pkg_meta.get("name", fname.split("-")[0]),
                    "version": str(pkg_meta.get("version", "1.0")),
                    "release": int(pkg_meta.get("release", 1)),
                    "architecture": pkg_meta.get("architecture", "x86_64"),
                    "summary": pkg_meta.get("summary", ""),
                    "requires": deps_meta.get("requires", []),
                    "provides": deps_meta.get("provides", []),
                    "conflicts": deps_meta.get("conflicts", []),
                    "replaces": deps_meta.get("replaces", []),
                }
            }

    expires = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")

    # 1. targets.json
    targets_signed = {
        "_type": "targets",
        "spec_version": TUF_SPEC_VERSION,
        "version": 1,
        "expires": expires,
        "targets": targets_dict,
    }
    targets_can = canonical_json(targets_signed)
    targets_sig = sign(tgt_priv, targets_can)
    targets_envelope = {
        "signatures": [{"keyid": "key-tgt", "sig": targets_sig}],
        "signed": targets_signed,
    }
    targets_path = os.path.join(repo_dir, "metadata", "targets.json")
    with open(targets_path, "wb") as f:
        f.write(json.dumps(targets_envelope, indent=2).encode('utf-8'))

    targets_sha256 = hashlib.sha256(open(targets_path, "rb").read()).hexdigest()
    targets_size = os.path.getsize(targets_path)

    # 2. snapshot.json
    snapshot_signed = {
        "_type": "snapshot",
        "spec_version": TUF_SPEC_VERSION,
        "version": 1,
        "expires": expires,
        "meta": {
            "targets.json": {
                "version": 1,
                "length": targets_size,
                "hashes": {"sha256": targets_sha256},
            }
        }
    }
    snapshot_can = canonical_json(snapshot_signed)
    snapshot_sig = sign(snap_priv, snapshot_can)
    snapshot_envelope = {
        "signatures": [{"keyid": "key-snap", "sig": snapshot_sig}],
        "signed": snapshot_signed,
    }
    snapshot_path = os.path.join(repo_dir, "metadata", "snapshot.json")
    with open(snapshot_path, "wb") as f:
        f.write(json.dumps(snapshot_envelope, indent=2).encode('utf-8'))

    snapshot_sha256 = hashlib.sha256(open(snapshot_path, "rb").read()).hexdigest()
    snapshot_size = os.path.getsize(snapshot_path)

    # 3. timestamp.json
    ts_expires = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
    ts_signed = {
        "_type": "timestamp",
        "spec_version": TUF_SPEC_VERSION,
        "version": 1,
        "expires": ts_expires,
        "meta": {
            "snapshot.json": {
                "version": 1,
                "length": snapshot_size,
                "hashes": {"sha256": snapshot_sha256},
            }
        }
    }
    ts_can = canonical_json(ts_signed)
    ts_sig = sign(ts_priv, ts_can)
    ts_envelope = {
        "signatures": [{"keyid": "key-ts", "sig": ts_sig}],
        "signed": ts_signed,
    }
    with open(os.path.join(repo_dir, "metadata", "timestamp.json"), "wb") as f:
        f.write(json.dumps(ts_envelope, indent=2).encode('utf-8'))

    # 4. root.json
    root_expires = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ")
    root_signed = {
        "_type": "root",
        "spec_version": TUF_SPEC_VERSION,
        "version": 1,
        "expires": root_expires,
        "consistent_snapshot": False,
        "keys": {
            "key-root": {"keytype": "ed25519", "scheme": "ed25519", "keyval": root_pub},
            "key-ts": {"keytype": "ed25519", "scheme": "ed25519", "keyval": ts_pub},
            "key-snap": {"keytype": "ed25519", "scheme": "ed25519", "keyval": snap_pub},
            "key-tgt": {"keytype": "ed25519", "scheme": "ed25519", "keyval": tgt_pub},
        },
        "roles": {
            "root": {"keyids": ["key-root"], "threshold": 1},
            "timestamp": {"keyids": ["key-ts"], "threshold": 1},
            "snapshot": {"keyids": ["key-snap"], "threshold": 1},
            "targets": {"keyids": ["key-tgt"], "threshold": 1},
        }
    }
    root_can = canonical_json(root_signed)
    root_sig = sign(root_priv, root_can)
    root_envelope = {
        "signatures": [{"keyid": "key-root", "sig": root_sig}],
        "signed": root_signed,
    }
    root_bytes = json.dumps(root_envelope, indent=2).encode('utf-8')
    for root_name in ("root.json", "1.root.json"):
        with open(os.path.join(repo_dir, "metadata", root_name), "wb") as f:
            f.write(root_bytes)

    # 5. Create Test Fixtures: Expired Metadata
    exp_ts_signed = dict(ts_signed)
    exp_ts_signed["expires"] = "2020-01-01T00:00:00Z"
    exp_ts_can = canonical_json(exp_ts_signed)
    exp_ts_sig = sign(ts_priv, exp_ts_can)
    with open(os.path.join(repo_dir, "metadata-expired", "timestamp.json"), "wb") as f:
        f.write(json.dumps({"signatures": [{"keyid": "key-ts", "sig": exp_ts_sig}], "signed": exp_ts_signed}, indent=2).encode('utf-8'))
    # Symlink or copy others
    shutil.copy2(os.path.join(repo_dir, "metadata", "root.json"), os.path.join(repo_dir, "metadata-expired", "root.json"))
    shutil.copy2(os.path.join(repo_dir, "metadata", "snapshot.json"), os.path.join(repo_dir, "metadata-expired", "snapshot.json"))
    shutil.copy2(os.path.join(repo_dir, "metadata", "targets.json"), os.path.join(repo_dir, "metadata-expired", "targets.json"))

    # 6. Create Test Fixtures: Rollback Metadata
    rb_ts_signed = dict(ts_signed)
    rb_ts_signed["version"] = 0
    rb_ts_can = canonical_json(rb_ts_signed)
    rb_ts_sig = sign(ts_priv, rb_ts_can)
    with open(os.path.join(repo_dir, "metadata-rollback", "timestamp.json"), "wb") as f:
        f.write(json.dumps({"signatures": [{"keyid": "key-ts", "sig": rb_ts_sig}], "signed": rb_ts_signed}, indent=2).encode('utf-8'))
    shutil.copy2(os.path.join(repo_dir, "metadata", "root.json"), os.path.join(repo_dir, "metadata-rollback", "root.json"))
    shutil.copy2(os.path.join(repo_dir, "metadata", "snapshot.json"), os.path.join(repo_dir, "metadata-rollback", "snapshot.json"))
    shutil.copy2(os.path.join(repo_dir, "metadata", "targets.json"), os.path.join(repo_dir, "metadata-rollback", "targets.json"))

    print(f"[repo-server] Initialized TUF repository at {repo_dir}")
    print(f"  Root pub: {root_pub}")
    print(f"  Packages indexed: {len(targets_dict)}")

def rotate_root(repo_dir):
    repo_dir = os.path.abspath(repo_dir)
    with open(os.path.join(repo_dir, "keys", "private_keys.json"), "r") as f:
        priv_keys = json.load(f)

    old_root_priv_bytes = bytes.fromhex(priv_keys["root"]["priv"])
    old_root_priv = ed25519.Ed25519PrivateKey.from_private_bytes(old_root_priv_bytes)
    old_root_pub = priv_keys["root"]["pub"]

    # Generate new root key
    new_root_priv, new_root_pub, new_root_priv_hex = gen_key()

    ts_pub = priv_keys["timestamp"]["pub"]
    snap_pub = priv_keys["snapshot"]["pub"]
    tgt_pub = priv_keys["targets"]["pub"]

    root_expires = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ")
    root_signed_v2 = {
        "_type": "root",
        "spec_version": TUF_SPEC_VERSION,
        "version": 2,
        "expires": root_expires,
        "consistent_snapshot": False,
        "keys": {
            "key-root": {"keytype": "ed25519", "scheme": "ed25519", "keyval": old_root_pub},
            "key-root-2": {"keytype": "ed25519", "scheme": "ed25519", "keyval": new_root_pub},
            "key-ts": {"keytype": "ed25519", "scheme": "ed25519", "keyval": ts_pub},
            "key-snap": {"keytype": "ed25519", "scheme": "ed25519", "keyval": snap_pub},
            "key-tgt": {"keytype": "ed25519", "scheme": "ed25519", "keyval": tgt_pub},
        },
        "roles": {
            "root": {"keyids": ["key-root-2"], "threshold": 1},
            "timestamp": {"keyids": ["key-ts"], "threshold": 1},
            "snapshot": {"keyids": ["key-snap"], "threshold": 1},
            "targets": {"keyids": ["key-tgt"], "threshold": 1},
        }
    }

    message = canonical_json(root_signed_v2)
    sig_old = sign(old_root_priv, message)
    sig_new = sign(new_root_priv, message)

    envelope_v2 = {
        "signatures": [
            {"keyid": "key-root", "sig": sig_old},
            {"keyid": "key-root-2", "sig": sig_new},
        ],
        "signed": root_signed_v2,
    }

    root_bytes = json.dumps(envelope_v2, indent=2).encode('utf-8')
    for root_name in ("root.json", "2.root.json"):
        root_path = os.path.join(repo_dir, "metadata", root_name)
        with open(root_path, "wb") as f:
            f.write(root_bytes)

    # Update private keys tracking
    priv_keys["root_v2"] = {
        "priv": new_root_priv_hex,
        "pub": new_root_pub,
        "keyid": "key-root-2"
    }
    with open(os.path.join(repo_dir, "keys", "private_keys.json"), "w") as f:
        json.dump(priv_keys, f, indent=2)
    os.chmod(os.path.join(repo_dir, "keys", "private_keys.json"), 0o600)

    print(f"[repo-server] Rotated TUF root key to version 2!")
    print(f"  Old Root pub: {old_root_pub}")
    print(f"  New Root pub: {new_root_pub}")
    print(f"  Signed by both key-root and key-root-2 (threshold met).")

class RangeRequestHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP Request Handler supporting Range headers and test routes"""
    def translate_path(self, path):
        # Route test endpoints to fixture subdirectories
        if path.startswith("/test-expired/metadata/"):
            rel_path = path[len("/test-expired/metadata/"):]
            return os.path.join(self.repo_dir, "metadata-expired", rel_path)
        if path.startswith("/test-rollback/metadata/"):
            rel_path = path[len("/test-rollback/metadata/"):]
            return os.path.join(self.repo_dir, "metadata-rollback", rel_path)
        return super().translate_path(path)

    def send_head(self):
        path = self.translate_path(self.path)
        if os.path.isdir(path):
            return super().send_head()
        try:
            f = open(path, 'rb')
        except OSError:
            self.send_error(404, "File not found")
            return None

        fs = os.fstat(f.fileno())
        total_length = fs.st_size

        range_header = self.headers.get('Range')
        if range_header:
            try:
                ranges = range_header.strip().split('=')[1].split('-')
                start = int(ranges[0])
                end = int(ranges[1]) if ranges[1] else total_length - 1
                if start >= total_length:
                    self.send_error(416, "Requested Range Not Satisfiable")
                    f.close()
                    return None
                length = end - start + 1
                self.send_response(206)
                self.send_header("Content-Type", self.guess_type(path))
                self.send_header("Content-Range", f"bytes {start}-{end}/{total_length}")
                self.send_header("Content-Length", str(length))
                self.send_header("Accept-Ranges", "bytes")
                self.end_headers()
                f.seek(start)
                return f
            except Exception:
                pass

        self.send_response(200)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Content-Length", str(total_length))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()
        return f

def serve_repo(repo_dir, port=8080):
    repo_dir = os.path.abspath(repo_dir)
    os.chdir(repo_dir)
    class CustomServer(RangeRequestHandler):
        pass
    CustomServer.repo_dir = repo_dir
    httpd = socketserver.TCPServer(("", port), CustomServer, bind_and_activate=False)
    httpd.allow_reuse_address = True
    httpd.server_bind()
    httpd.server_activate()
    print(f"[repo-server] Serving {repo_dir} on http://0.0.0.0:{port} with Range support...")
    try:
        httpd.serve_forever()
    finally:
        httpd.server_close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    init_p = sub.add_parser("init")
    init_p.add_argument("--repo-dir", default="build/repo")
    init_p.add_argument("--pkgs-dir", default="build/packages")

    rot_p = sub.add_parser("rotate-root")
    rot_p.add_argument("--repo-dir", default="build/repo")

    serve_p = sub.add_parser("serve")
    serve_p.add_argument("--repo-dir", default="build/repo")
    serve_p.add_argument("--port", type=int, default=8080)

    args = parser.parse_args()
    if args.cmd == "init":
        init_repo(args.repo_dir, args.pkgs_dir)
    elif args.cmd == "rotate-root":
        rotate_root(args.repo_dir)
    elif args.cmd == "serve":
        serve_repo(args.repo_dir, args.port)
