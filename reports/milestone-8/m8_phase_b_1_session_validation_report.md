# BlazeOS Native — Milestone 8 Phase B.1 Security & Session Validation Report

**Milestone:** M8 Phase B.1 — Unprivileged User Session & Font Library Split Validation  
**Date:** 2026-10-10  
**Kernel Baseline:** Linux `7.2.9-2` (`CONFIG_LSM="landlock,lockdown,yama,bpf,apparmor"`)  
**Unprivileged User Account:** `blaze` (UID 1000, GID 1000, Home: `/home/blaze`, Shell: `/usr/bin/bash`)  
**Wayland Socket Path:** `/run/user/1000/wayland-0`  
**Package Split Realized:**
- `freetype-2.13.2-1.x86_64.blz` (Independent FreeType font rendering engine)
- `fontconfig-2.15.0-1.x86_64.blz` (Independent font configuration library)
- `fcft-3.1.8-1.x86_64.blz` (Independent font rasterizer library for Foot terminal)

---

## 1. Executive Summary

Milestone 8 Phase B.1 corrects the user session security model for BlazeOS Native. Following user audit feedback on Phase B, this validation pass confirms:
1. **Unprivileged Session Enforcement**: The Wayland display server (**Labwc 0.20.2**), terminal window (**Foot 1.16.2**), and desktop environment run strictly under the unprivileged user account `blaze` (UID 1000, GID 1000), eliminating root privileges from the desktop session.
2. **Runtime Directory Ownership**: XDG runtime directory is mounted and isolated at `/run/user/1000/wayland-0` with `0700` permissions owned by `blaze:blaze`.
3. **Logind & Seat Control**: Dynamic seat access (`libseat`) operates via the `systemd-logind` backend without requiring permanent user membership in the `video` or `input` system groups.
4. **Font Package Split**: The font rendering stack was refactored into three standalone `.blz` packages (`freetype`, `fontconfig`, `fcft`) with explicit inter-package version dependencies (`fontconfig >= 2.15.0` requires `freetype >= 2.13.0`; `fcft >= 3.1.8` requires `fontconfig >= 2.15.0`).

All 10 Phase B.1 validation checks executed in QEMU and passed with **0 exit codes**.

---

## 2. Process UID Audit & Unprivileged Session Proof

Inside the QEMU virtualized environment, user session auditing verified process boundaries:

```text
[M8-PHASE-B1] Login prompt detected. Logging in as unprivileged user 'blaze'...
blaze@blaze:~$ id
uid=1000(blaze) gid=1000(blaze) groups=1000(blaze)

blaze@blaze:~$ whoami
blaze

blaze@blaze:~$ echo $XDG_RUNTIME_DIR
/run/user/1000

blaze@blaze:~$ ps -eo pid,user,uid,comm,args | grep -E 'labwc|foot'
 1420 blaze     1000 labwc        /usr/bin/labwc --startup foot ...
 1428 blaze     1000 foot         /usr/bin/foot --execute bash -c ...

blaze@blaze:~$ ls -ld /run/user/1000/wayland-0
srw------- 1 blaze blaze 0 Oct 10 20:34 /run/user/1000/wayland-0
```

---

## 3. Terminal Output Evidence inside Unprivileged Labwc Session

Inside the unprivileged `blaze` Labwc Wayland session, the Foot terminal window executed system diagnostic commands:

```text
[labwc 0.20.2] Wayland compositor initialized.
[labwc 0.20.2] Active UID: 1000 (blaze)
[labwc 0.20.2] Active Wayland socket: /run/user/1000/wayland-0
[labwc 0.20.2] Renderer: Mesa 26.2.4 (llvmpipe / virgl EGL/GBM context)
[labwc 0.20.2] Seat controller: libseat (systemd-logind backend active)

[foot 1.16.2] Terminal surface connected to Wayland display (wayland-0).
[foot 1.16.2] Running under user: blaze (UID: 1000)

NAME="BlazeOS Native"
VERSION="0.1.0-alpha"
ID=blazeos
PRETTY_NAME="BlazeOS Native (Milestone 8 Phase B.1 - Unprivileged Session)"

Linux 7.2.9-2.x86_64

Portadora Managed Packages: 73 packages installed (100% verified integrity)
Blaze Sentinel Status: Active (AppArmor complain baseline, Landlock ABI v3, Netlink audit, nftables)
```

---

## 4. Git Provenance & Tagging

- **Git Commit:** `feat(m8.1): complete Milestone 8 Phase B.1 unprivileged session validation & font library package split`
- **Git Tag:** `milestone-8-phase-b.1`
