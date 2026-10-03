# Blaze Base v0.1 Specification

## 1. Overview & Vision
Blaze Base is the independent, foundational tier of the **Blaze Universe** ecosystem. It is **not** a downstream respin of Fedora, Debian, or Arch. It defines its own package repository, system rootfs layout, bootstrap pipeline, and binary format via **Portadora**.

---

## 2. Target Platform & Scope Freeze (v0.1)

To prevent scope creep and maintain strict engineering discipline, the target specifications for v0.1 are fixed:

| Component | Target Specification | Rationale |
| :--- | :--- | :--- |
| **Architecture** | `x86_64` (baseline `x86-64-v2` / `x86-64`) | Industry standard 64-bit desktop/server baseline. |
| **C Library** | GNU C Library (`glibc`) 2.38+ | Full ABI compatibility with standard Linux userland and future foreign packages. |
| **Filesystem Hierarchy** | Strict **UsrMerge** (FHS 3.0 modern) | Clean separation of vendor `/usr` and host `/etc`, `/var`. |
| **Init System** | `systemd` | Service orchestration, unified cgroups v2, journald, udev. |
| **Boot Mechanism** | `UEFI` (x86_64-efi) via `systemd-boot` / GRUB2 | Modern firmware standard without legacy BIOS bloat. |

---

## 3. Filesystem Layout (Strict UsrMerge)

Blaze Base mandates an absolute UsrMerge layout. No binaries or libraries reside directly under `/bin`, `/sbin`, `/lib`, or `/lib64`. They are deterministic symlinks into `/usr`.

```
/
├── bin -> usr/bin
├── sbin -> usr/bin
├── lib -> usr/lib
├── lib64 -> usr/lib
├── usr/
│   ├── bin/              # All executables
│   ├── lib/              # All shared objects (.so)
│   ├── include/          # Development headers
│   ├── share/            # Architecture-independent assets (man, doc, locale)
│   └── lib/systemd/      # Vendor systemd units
├── etc/                  # Host-specific configuration (kept minimal by packages)
├── var/                  # Variable state, logs, spool
│   ├── lib/
│   │   └── portadora/    # Package manager database & lockfiles
│   └── log/
├── run/                  # Volatile runtime data (tmpfs)
├── dev/                  # Device nodes (devtmpfs)
├── proc/                 # Process virtual filesystem (procfs)
├── sys/                  # Kernel object filesystem (sysfs)
├── tmp/                  # Temporary directory (tmpfs)
├── root/                 # Root home directory
├── home/                 # User homes
├── mnt/                  # Mount point
└── opt/                  # Optional add-on software
```

### Dynamic Linker Canonical Path
- Canonical: `/usr/lib/ld-linux-x86-64.so.2`
- Compatibility Symlink: `/lib64/ld-linux-x86-64.so.2 -> /usr/lib/ld-linux-x86-64.so.2`

---

## 4. Standard Build Environment & Toolchain Specs

### Compilation Defaults
Packages built for Blaze Base must adhere to the following flags to guarantee security and deterministic execution:
```bash
export CFLAGS="-O2 -pipe -fexceptions -Wp,-D_FORTIFY_SOURCE=2 -Wp,-D_GLIBCXX_ASSERTIONS -fstack-protector-strong --param=ssp-buffer-size=4 -grecord-gcc-switches -fasynchronous-unwind-tables"
export CXXFLAGS="$CFLAGS"
export LDFLAGS="-Wl,-z,relro -Wl,-z,now -Wl,--as-needed"
```

### Standard Triplet
- Target Triplet: `x86_64-blaze-linux-gnu` (or `x86_64-unknown-linux-gnu` during early bootstrap)

---

## 5. Milestone 1: Minimal Base Package Set

For Milestone 1 self-verification, the following packages are required in `.blz` format:

1. **`filesystem`**:
   - Creates the UsrMerge symlinks (`/bin`, `/lib`, etc.).
   - Standard directory permissions (`0755`, `/tmp` `1777`, `/root` `0700`).
   - `/etc/os-release`, `/etc/passwd`, `/etc/group`, `/etc/shells`.
2. **`glibc`**:
   - Core C runtime (`libc.so.6`, `libm.so.6`, `libpthread.so.0`, `ld-linux-x86-64.so.2`).
   - Locales, basic timezone data.
3. **`bash`**:
   - The primary interactive and scripting shell (`/usr/bin/bash`, symlink `/usr/bin/sh`).
4. **`coreutils`**:
   - Foundational UNIX utilities (`cat`, `ls`, `mkdir`, `cp`, `mv`, `rm`, `chmod`, `chown`, etc.).
5. **`portadora`**:
   - The native package manager binary (`/usr/bin/portadora`).

---

## 6. Milestone 1 Acceptance Criteria

A host system boots or chroots into the generated rootfs and validates without external dependencies:

```bash
$ sudo chroot build/rootfs /usr/bin/bash
root@blaze:/# cat /etc/os-release
NAME="BlazeOS"
ID=blaze
PRETTY_NAME="BlazeOS Native (Blaze Universe)"
VERSION_ID="0.1"

root@blaze:/# portadora list
filesystem 0.1-1
glibc 2.39-1
bash 5.2.21-1
coreutils 9.4-1
portadora 0.1.0-1

root@blaze:/# portadora verify
All managed files verified.
```
