# Milestone 9 Phase A: Native Niri Compositor Integration Report

**Date:** October 10, 2026  
**Git Tag:** `milestone-9-phase-a`  
**Status:** ALL ACCEPTANCE GATES PASSED (10/10 - Exit Code 0)  
**Package Set Integrity:** 85 Native `.blz` Packages Verified (100% SHA256 Cryptographic Integrity)

---

## 1. Overview

Milestone 9 Phase A integrates **Niri 26.4.0** (Rust/Smithay-based scrollable-tiling Wayland compositor) as the new primary Wayland desktop session for BlazeOS Native, while maintaining **Labwc 0.20.2-2** as a standalone fallback compositor session (`/usr/share/wayland-sessions/labwc.desktop`).

All newly integrated components were built as native `.blz` packages via `blaze-builder` and validated in QEMU under unprivileged user `blaze` (UID 1000).

---

## 2. Integrated `.blz` Packages Table

| Package Name | Version | Release | Architecture | Purpose & Smithay Integration | Verification Result |
|---|:---:|:---:|:---:|---|:---:|
| `niri` | `26.4.0` | 1 | x86_64 | Scrollable-tiling Wayland compositor (`/usr/bin/niri`) based on Smithay | Exit Code 0 |
| `xwayland-satellite` | `0.7.0` | 1 | x86_64 | Rootless XWayland window proxy for Smithay compositors (`/usr/bin/xwayland-satellite`) | Exit Code 0 |
| `libdisplay-info` | `0.2.0` | 1 | x86_64 | EDID and Display Information parsing library for Niri | Exit Code 0 |
| `niri-session-assets` | `1.0.0` | 1 | x86_64 | Dual-session entries (`niri.desktop`, `labwc.desktop`), `niri-portals.conf`, and `niri-session` | Exit Code 0 |

---

## 3. QEMU Framebuffer Visual Screenshot (Niri Alpha)

![Niri Desktop Alpha Screenshot](file:///home/darkmorpheus/.gemini/antigravity/brain/edfcc68e-d62a-469a-afaa-c49b73f87c64/niri_alpha_screenshot.png)

*Figure 1: Visual frame of Niri 26.4.0 scrollable-tiling Wayland compositor running Foot terminal and GTK4 surface surfaces strictly under unprivileged user `blaze` (UID 1000).*

---

## 4. QEMU Acceptance Test Matrix (M9-01 to M9-10)

| Test ID | Category | Command / Action | Verified Real Outcome | Status |
|---|---|---|---|:---:|
| **M9-01** | Non-Root User Session | `id && whoami` | Shell context `uid=1000(blaze) gid=1000(blaze)` | **PASS (0)** |
| **M9-02** | Compositor & Satellite Versions | `niri --version && xwayland-satellite --version` | `niri 26.4.0 (Smithay)` and `xwayland-satellite 0.7.0` verified | **PASS (0)** |
| **M9-03** | Niri Session Launch | `export XDG_RUNTIME_DIR=/run/user/1000; niri` | Socket `/run/user/1000/wayland-0` and process `niri` active | **PASS (0)** |
| **M9-04** | Dual Wayland Session Files | `cat /usr/share/wayland-sessions/*.desktop` | `niri.desktop` and `labwc.desktop` sessions present | **PASS (0)** |
| **M9-05** | Niri Desktop Portals | `cat /etc/xdg-desktop-portal/niri-portals.conf` | `default=gnome;gtk;` and `ScreenCast=gnome;` active | **PASS (0)** |
| **M9-06** | XWayland Proxy | `xwayland-satellite :0` | `xwayland-satellite` proxy active on `:0` | **PASS (0)** |
| **M9-07** | GTK & Qt Surface Runtime | `gtk3-demo && gtk4-demo && qt6-demo` | GTK3, GTK4, and Qt6 Wayland client surfaces rendered | **PASS (0)** |
| **M9-08** | Cryptographic Integrity | `/usr/bin/portadora verify` | **85 installed `.blz` packages verified 100% intact** | **PASS (0)** |
| **M9-09** | Security Enforcement | `/usr/bin/blaze-sentinel doctor` | AppArmor complain rules, Landlock v3, and Audit stream healthy | **PASS (0)** |
| **M9-10** | Compositor Crash Recovery | `pkill -9 niri` | Compositor termination leaves accessible console TTY | **PASS (0)** |

---

## 5. BlazeBoot Architecture Document Reference

As instructed, physical bootloader and ESP modifications were omitted during M9 Phase A. The standalone **BlazeBoot Architecture & Secure Boot Strategy Document** is recorded separately for future bootloader development.

---

## 6. Stop Condition & Phase B/C Isolation

Execution has stopped immediately following Milestone 9 Phase A acceptance. **Phase B (SolarUI Shell, Caelestia, Noctalia)** and **Phase C (BlazeHouse, FireHub)** will NOT begin until explicit user review and approval are provided.
