# BlazeOS Native — Milestone 4 Acceptance Report
**Milestone:** Networking & Secure Connectivity (Blaze Universe)  
**Date:** 2026-10-09  
**Kernel:** Linux `7.2.8 #2 SMP PREEMPT_DYNAMIC` (NFTables enabled)  
**Toolchain:** glibc `2.44`, binutils `2.47`, GCC `16.2.0`, Rust `1.98.1`  
**Package Manager:** Portadora `0.1.0`  
**Rootfs Package Count:** 55 packages (`portadora verify`: All managed files verified)

---

## 1. Executive Summary

Milestone 4 delivers foundational networking and secure connectivity to BlazeOS Native while upholding strict architectural invariants:
- **Zero untracked files**: Every binary, configuration file, helper, library, and systemd unit was packaged into pure `.blz` archives and installed through transactional Portadora operations.
- **Pure Systemd Network Stack**: `systemd-networkd` and `systemd-resolved` manage IP links and DNS resolution with no foreign network managers.
- **Stateful Sentinel Firewall**: `nftables` loaded at early boot with default drop policy on `input` and `forward`, allowing loopback and established/related traffic.
- **Modern Cryptography & Trust**: Mozilla NSS Root CA bundle (`ca-certificates`) and OpenSSL 3.6.4 provide verified TLS 1.3 connectivity; bad/untrusted certificates are rejected as required.
- **Secure Remote Management**: OpenSSH 10.5p1 configured with privilege separation (`sshd-session`, `sshd-auth`), pre-generated host keys, and systemd presets strictly keeping `sshd` inactive by default.
- **Crash & Reboot Resilience**: Multi-stage testing confirmed graceful `systemctl reboot` and persistence of firewall rules, network links, disabled SSH preset, and 100% Portadora file integrity.

---

## 2. Milestone 4 Package Matrix

| Package | Version | Provides / Purpose | Portadora Verification |
|---|---|---|---|
| `filesystem` | `0.1.0-3` | System users (`systemd-network`, `systemd-resolve`, `sshd`), `nologin` symlink, FHS layout | Verified |
| `jansson` | `2.14-1` | `libjansson.so.4` (JSON AST support for nftables) | Verified |
| `libmnl` | `1.0.5-1` | Minimalistic Netlink communication library (`libmnl.so.0`) | Verified |
| `libnftnl` | `1.3.0-1` | Netfilter netlink interface library (`libnftnl.so.11`) | Verified |
| `nftables` | `1.1.7-1` | User-space packet filtering utility (`/usr/bin/nft`), `nftables.service`, `/etc/nftables.conf` | Verified |
| `iproute2` | `7.2.0-1` | Routing & link management tools (`ip`, `ss`, `bridge`, `tc`, `rtmon`) | Verified |
| `iputils` | `20240905-1` | Diagnostic utilities (`/usr/bin/ping`, `/usr/bin/tracepath`) | Verified |
| `ca-certificates` | `2026.09-1` | Extracted Mozilla NSS CA trust anchors (`/etc/ca-certificates/extracted/tls-ca-bundle.pem`) | Verified |
| `curl` | `8.22.0-1` | HTTPS transfer CLI (`/usr/bin/curl`) linked against OpenSSL 3.6.4 and trusted anchors | Verified |
| `openssh` | `10.5p1-3` | SSH suite (`ssh`, `sshd`, `scp`, `sftp`, `sshd-session`, `sshd-auth`, `empty.sshd` privsep) | Verified |
| `blaze-network-config` | `0.1.0-2` | `networkctl`, `resolvectl`, `80-dhcp.network`, systemd presets (`disable *`, `disable sshd`) | Verified |
| `linux-blaze` | `7.2.8-2` | Linux 7.2.8 kernel with `CONFIG_NF_TABLES=y`, `CONFIG_NF_CONNTRACK=y`, `CONFIG_NETFILTER_XT_TARGET_LOG=y` | Verified |

---

## 3. Acceptance Test Results Matrix

| ID | Test Scenario | Verified Behavior | Exit Code | Result |
|---|---|---|---|---|
| **NET-01** | VirtIO Link Detection | `ip -d link show` detected `eth0` with virtio driver, state UP | 0 | **PASS** |
| **NET-02** | DHCP Lease & Routing | `networkctl status` showed `routable`, acquired `10.0.2.15/24`, default gateway `10.0.2.2` | 0 | **PASS** |
| **NET-03** | DNS Resolution | `resolvectl status` active on `10.0.2.3`, `getent hosts kernel.org` resolved IPv4 & IPv6 | 0 | **PASS** |
| **NET-04** | HTTPS TLS 1.3 & CA Trust | `curl -Iv https://kernel.org` completed TLS 1.3 handshake with `OpenSSL verify result: 0`, HTTP/2 200 | 0 | **PASS** |
| **NET-05** | Negative Security (BadSSL) | `curl https://self-signed.badssl.com/` rejected with `BADSSL_REJECTED_AS_EXPECTED` | 0 | **PASS** |
| **NET-06** | nftables Active Ruleset | `systemctl status nftables` active, `nft list ruleset` confirmed `policy drop` on input/forward | 0 | **PASS** |
| **NET-07** | Loopback & ICMP Filtering | `ping -c 2 127.0.0.1` passed with 0% packet loss | 0 | **PASS** |
| **NET-08** | Interface Cycle & DHCP Recovery | `eth0` brought down then up, successfully re-acquired `10.0.2.15/24` | 0 | **PASS** |
| **NET-09** | OpenSSH Controlled Activation | Inactive by default; started on-demand via systemd; `ss -tlpn` showed `LISTEN :22` | 0 | **PASS** |
| **NET-10** | Portadora Package Integrity | `portadora verify` returned `All managed files verified.` across all 55 packages | 0 | **PASS** |
| **NET-11** | Graceful Reboot & Post-Reboot Health | `systemctl reboot` cleanly rebooted, re-verified DHCP, nftables, curl, SSH inactive, and poweroff | 0 | **PASS** |

---

## 4. Test Execution Log Summary
Captured in `reports/milestone-4/m4_test_output.log`:
- QEMU environment: `x86_64`, KVM host acceleration, OVMF UEFI, VirtIO Net with host forward `2222:22`.
- Initial boot: Clean login prompt reached in ~1.2s.
- Reboot cycle: `systemd-shutdown` unmounted all filesystems, cleanly rebooted kernel `7.2.8 #2`.
- Second boot: Immediate interface acquisition, `sshd` remained inactive (`SSHD_INACTIVE_POST_REBOOT`), Portadora verified all files, and `systemctl poweroff` powered down the VM cleanly (`reboot: Power down`).
