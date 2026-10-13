<div align="center">

# 🌌 BlazeOS Native — Blaze Universe

**An independent, modern, high-performance Linux distribution built from source.**  
*Not a fork. Not a respin. Engineered from scratch with Rust, Wayland, and strict cryptographic integrity.*

[![License: MIT/GPL](https://img.shields.io/badge/license-MIT%2FGPL-blue.svg)](LICENSE)
[![Kernel: Linux 7.2.9](https://img.shields.io/badge/kernel-Linux%207.2.9-orange.svg)](https://kernel.org)
[![Display: Wayland Niri](https://img.shields.io/badge/compositor-Niri%2026.04-green.svg)](https://github.com/YaLTeR/niri)
[![Shell: SolarUI / Noctalia](https://img.shields.io/badge/shell-Noctalia%205.1.0%20%2B%20SolarUI-purple.svg)](#solar-shell--desktop-environment)
[![Package Manager: Portadora](https://img.shields.io/badge/package%20manager-Portadora%20(Rust)-red.svg)](#portadora-package-manager)
[![Architecture: x86_64](https://img.shields.io/badge/arch-x86__64--v2-yellow.svg)](#target-platform)

</div>

---

## 🌟 Overview & Vision

**BlazeOS Native** is the foundational operating system of the **Blaze Universe** ecosystem. 

Unlike traditional distributions that layer scripts over Debian, Ubuntu, Fedora, or Arch Linux, BlazeOS Native is an **autonomous distribution built entirely from source**. It establishes its own:
- **Portadora Package Manager:** Written in Rust, utilizing the Zstandard-compressed `.blz` container format and TUF (The Update Framework) cryptographic verification.
- **Blaze Builder (`blaze-builder`):** Declarative, deterministic TOML package recipes (`recipe.toml`) compiling a unified Linux userland.
- **Solar Shell (SolarUI):** A modern Wayland-native desktop environment orchestrated by a Rust supervisor (`solar-core`), powered by the **Niri** scrollable tiling compositor and native **Noctalia 5.1.0** C++ desktop shell (with Caelestia integration options).
- **Strict UsrMerge Architecture:** Clean, deterministic FHS 3.0 layout where `/usr` holds all vendor state, `/etc` stores local host configuration, and `/var` manages runtime state.
- **3.8-Second Sub-Second Boot:** Streamlined `systemd` service orchestration, optimized kernel parameters, and zero-timeout direct seat handoff into Wayland.

---

## 🏗️ Architecture & Technology Stack

```
+--------------------------------------------------------------------------+
|                        BLAZE DESKTOP EXPERIENCE                          |
|         Noctalia 5.1.0 Native C++ Shell  |  SolarUI / Caelestia          |
+--------------------------------------------------------------------------+
|                 NIRI 26.04 SCROLLABLE WAYLAND COMPOSITOR                 |
|               Solar Shell Supervisor (solar-core in Rust)                |
+--------------------------------------------------------------------------+
|                      PORTADORA PACKAGE ECOSYSTEM                         |
|   .blz Container Format  |  TUF Cryptographic Anchor  |  blaze-builder   |
+--------------------------------------------------------------------------+
|                         SYSTEMD 255 INIT & IPC                           |
|       seatd (Seat Management) | D-Bus Message Bus | PAM & Shadow Auth    |
+--------------------------------------------------------------------------+
|                    CANONICAL USRMERGE USERLAND (GLIBC)                   |
|      /usr/bin | /usr/lib | /usr/share (Deterministic symlinks at root)   |
+--------------------------------------------------------------------------+
|                  LINUX KERNEL 7.2.9 (x86_64 PREEMPT)                     |
|         VirtIO GPU/Tablet/Net | KMS/DRM Drivers | Evdev & Seatd          |
+--------------------------------------------------------------------------+
```

### 1. Portadora Package Manager (`crates/portadora`)
Portadora is designed in Rust for memory safety, cryptographic integrity, and extreme speed:
- **`.blz` Package Container:**
  - `manifest.toml`: Rich metadata, dependency graphs, virtual provides (`cmd:*`, `so:*`), and maintainer information.
  - `files.json`: Exact file permissions, sizes, and per-file SHA-256 hashes for 100% tamper-evident verification.
  - `data.tar.zst`: Ultra-fast multi-threaded Zstandard compressed payload extracted directly into the sysroot.
- **TUF Security (The Update Framework):**
  - Cryptographically signed repository metadata using `ed25519` keypairs (`root.json`, `targets.json`, `snapshot.json`, `timestamp.json`).
  - Protected against freeze attacks, rollback attacks, and key compromises.
- **Transactional & Resilient:**
  - Built-in local cache scanning (`/var/cache/portadora/packages/`).
  - Strict system verification via `portadora verify` to detect modified or corrupted files.

### 2. Solar Shell & Desktop Environment
- **Compositor:** Niri 26.04 — Modern scrollable tiling Wayland compositor.
- **Desktop Shell:** Noctalia 5.1.0 — Native C++ Wayland desktop shell providing a status bar, calendar, audio controls, power menu, network indicators, and application launcher.
- **Supervisor (`solar-core`):** Rust supervisor ensuring watchdog monitoring, automatic restart on crash, and clean process isolation.
- **Input & Display:** Full native seat management (`seatd`), hardware-accelerated cursor, and absolute VirtIO tablet pointer integration.

### 3. File Hierarchy Standard (Strict UsrMerge)
All binaries and dynamic libraries reside in `/usr`:
- `/bin` ➔ `usr/bin`
- `/sbin` ➔ `usr/bin`
- `/lib` ➔ `usr/lib`
- `/lib64` ➔ `usr/lib`
- Canonical Dynamic Linker: `/usr/lib/ld-linux-x86-64.so.2`

---

## 🚀 Quickstart: Running BlazeOS Native

### Prerequisites
- Linux host with KVM enabled (`/dev/kvm`).
- QEMU (`qemu-system-x86_64`) with VirtIO and audio support.
- Python 3.10+ (for test orchestration).

### Boot the Live Desktop (QEMU KVM)
Clone the repository and launch the ready-to-run disk image:

```bash
git clone https://github.com/DarkMorpheus-pc/Blaze-Universe-.git
cd Blaze-Universe-

# Run BlazeOS Native with KVM, VirtIO tablet, and audio support
./tools/run-blazeos-native.sh
```

### Live Session Credentials
| Account | Password | Privileges | Default Shell |
| :--- | :--- | :--- | :--- |
| `blaze` | `blaze` | `sudo` enabled | `/bin/bash` |
| `root` | *(empty / sudo)* | System Administrator | `/bin/bash` |

*The system boots straight into the SolarUI Wayland desktop in approximately 3.8 seconds.*

---

## ⌨️ Desktop Shortcuts

| Shortcut | Action |
| :--- | :--- |
| `Super + Return` | Open Alacritty Terminal |
| `Super + D` / `Super + Space` | Toggle Application Launcher |
| `Super + Shift + Q` | Close Active Window |
| `Super + Left / Right` | Scroll Workspace Columns |
| `Super + Shift + E` | Power Menu / Exit Session |

---

## 📦 Portadora Package Commands

```bash
# List all installed packages
portadora list

# Inspect detailed package metadata
portadora info fastfetch

# Install a package from repository or local cache
portadora install ncurses

# Verify full filesystem integrity against package hashes
portadora verify
```

---

## 🛠️ Building From Source

BlazeOS packages are declared using clean TOML recipes in `recipes/core/`:

```bash
# Build a recipe with blaze-builder
cargo run --release -p blaze-builder -- recipes/core/fastfetch/recipe.toml

# The compiled package is generated at:
# build/packages/fastfetch-2.69.0-1.x86_64.blz

# Reassemble the bootable GPT disk image:
python3 tools/assemble_m8_disk.py
```

---

## 🌐 Distribution & Mirror Architecture

To ensure high availability, redundancy, and scalable bandwidth, the Blaze Universe uses a multi-tier mirror network:

| Tier / Platform | Role | Contents |
| :--- | :--- | :--- |
| **GitHub** (`Blaze-Universe-`) | Primary Source Repository & CI/CD | Source code, Rust crates, `recipes/core/*.toml`, tooling, issue tracking. |
| **GitHub Releases** | Binary Releases & Staging | Stable milestone disk images (`.raw.zst`), initial `.iso`, core `.blz` releases. |
| **SourceForge Mirror** | Global Binary Package Pool & Mirrors | High-bandwidth mirror hosting `/pool/core/*.blz`, repository manifests, and daily builds. |
| **Internet Archive (archive.org)** | Cold Storage & Historical Archives | Permanent, immutable archives of bootstrap toolchains, release milestones, and raw disk images. |

---

## 📁 Repository Structure

```
Blaze-Universe-/
├── crates/
│   ├── blaze-builder/      # TOML recipe parser and .blz package builder
│   ├── portadora/          # CLI package manager client
│   └── portadora-core/     # Package format, TUF validation, dependency engine
├── recipes/
│   └── core/               # 100+ Core package build recipes (glibc, kernel, niri, etc.)
├── tools/
│   ├── run-blazeos-native.sh     # Interactive QEMU runner script
│   ├── assemble_m8_disk.py       # GPT disk image partitioner and rootfs assembler
│   └── test-qemu-*.py            # Automated integration & acceptance test harness
├── docs/
│   └── specs/              # Formal specifications (Blaze Base, BLZ Format, Portadora)
└── Cargo.toml              # Cargo workspace manifest
```

---

## 🗺️ Roadmap & Milestones

- [x] **Milestone 1–4:** Toolchain bootstrap, glibc 2.38+, UsrMerge rootfs layout.
- [x] **Milestone 5:** Portadora package manager with TUF cryptographic verification.
- [x] **Milestone 6–7:** Linux kernel integration, systemd orchestration, and security hardening.
- [x] **Milestone 8:** Multi-package resolution, networking, and user authentication (PAM/Shadow).
- [x] **Milestone 9:** Native Wayland desktop (Niri 26.04), Noctalia 5.1.0 Shell, fast boot optimization (<4s).
- [ ] **Milestone 10:** Live distribution and graphical installer.
  - [x] **Phase A:** Hybrid BIOS/UEFI Live ISO, SquashFS root, and writable tmpfs OverlayFS.
  - [ ] **Phase B:** Safe target-disk deployment engine and graphical Solar Installer.
    - [x] **Phase B.1:** Non-destructive disk discovery, safety validation, and versioned install planning.
    - [x] **Phase B.2:** Transactional deployment to a disposable target disk with UEFI/BIOS boot verification.
    - [ ] **Phase B.3:** Recovery, rollback metadata, failure injection, and installer safety hardening.
    - [ ] **Phase B.4:** User, locale, timezone, keyboard, and graphical Solar Installer workflow.
- [ ] **Milestone 11:** Multi-architecture support (`aarch64` / ARM64).

---

## 📄 License

BlazeOS system components, Portadora, and Blaze-Builder are distributed under the **MIT License**.  
Upstream software (Linux Kernel, systemd, GNU toolchain) retains their respective upstream open-source licenses (GPLv2, LGPLv2.1+, GPLv3+).

---

<div align="center">
<b>Designed & Developed by the Blaze Universe Team</b><br>
<i>"Speed, Simplicity, and Sovereignty in Modern Computing."</i>
</div>
