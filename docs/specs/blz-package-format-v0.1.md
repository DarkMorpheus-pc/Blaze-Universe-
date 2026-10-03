# BLZ Package Format Specification v0.1

## 1. Overview
The `.blz` package is the native binary distribution format for **BlazeOS Native**. It is engineered for:
- Maximum decompression speed and compression ratio using **Zstandard (`zstd`)**.
- Predictable, deterministic, reproducible package builds.
- Clear structural separation between package metadata and the filesystem payload.
- Cryptographic integrity verification per-file and per-package.

---

## 2. Container Structure

A `.blz` file is an uncompressed or outer tar container containing standard entries, or a dual-stream tar archive. For v0.1, the canonical structure is an outer tarball with a strict structure:

```
package-name-1.0.0-1.x86_64.blz (tar archive)
├── manifest.toml         # Human-readable and machine-parseable metadata
├── files.json            # Deterministic file list with permissions, sizes, sha256
└── data.tar.zst          # Root-relative payload compressed with zstd
```

### 2.1. Advantages of this Structure
1. **Instant Inspection (`portadora info`):** Only `manifest.toml` and `files.json` need to be decompressed and read without touching `data.tar.zst`.
2. **Streaming Extraction:** When installing, `data.tar.zst` is piped directly into the zstd decompressor and extracted into the target sysroot (`--root`).

---

## 3. Metadata Specification: `manifest.toml`

Every `.blz` package must contain a top-level `manifest.toml` matching the following TOML schema:

```toml
[package]
name = "bash"
version = "5.2.21"
release = 1
architecture = "x86_64"
summary = "GNU Bourne-Again SHell"
description = "Bash is an sh-compatible command language interpreter that executes commands read from standard input or a file."
license = "GPL-3.0-or-later"
maintainer = "BlazeOS Core Team <core@blazeos.org>"
url = "https://www.gnu.org/software/bash/"

[dependencies]
# Direct package dependencies with optional version constraints
requires = [
    "glibc >= 2.38"
]

# Capabilities and virtual provides (including SONAMEs for library resolution)
provides = [
    "sh = 5.2.21",
    "cmd:bash",
    "cmd:sh"
]

# Packages incompatible with this package
conflicts = []

[build]
builder = "blaze-builder 0.1.0"
timestamp = 1717171717
source_url = "https://ftp.gnu.org/gnu/bash/bash-5.2.21.tar.gz"
source_sha256 = "c08272596be1131109ff6ab3c2d49e6d0144f77241be29ef4f85e49bc6a47a16"

[triggers]
# System hooks triggered upon installation (e.g. ldconfig, systemd-sysusers)
run_ldconfig = false
update_icon_cache = false
```

---

## 4. File Manifest: `files.json`

To enable instantaneous `portadora verify` without reading or unpacking payloads, `files.json` records every entry installed by the package:

```json
[
  {
    "path": "usr/bin/bash",
    "type": "file",
    "mode": "0755",
    "size": 1342120,
    "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "symlink_target": null
  },
  {
    "path": "usr/bin/sh",
    "type": "symlink",
    "mode": "0777",
    "size": 0,
    "sha256": null,
    "symlink_target": "bash"
  }
]
```

---

## 5. Payload: `data.tar.zst`

The payload contains the exact directory hierarchy intended for `/usr` and `/etc`:
- All paths are relative (e.g., `usr/bin/bash`, never `/usr/bin/bash`).
- Ownership is normalized to `root:root` (`uid=0`, `gid=0`).
- Modification timestamps (`mtime`) are clamped to the build timestamp or UTC epoch for reproducible builds.
- Compression: `zstd` with compression level 19 for release repositories, or level 3 for rapid local iteration.

---

## 6. Naming Conventions

Package filenames must strictly adhere to:
```
<name>-<version>-<release>.<architecture>.blz
```
*Example:* `glibc-2.39-1.x86_64.blz`
