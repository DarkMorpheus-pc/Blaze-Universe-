# BlazeOS Native — Milestone 5 Acceptance Report
**Milestone:** Portadora Repository, Secure Updates & Crash-Resilient Transactions (Blaze Universe)  
**Date:** 2026-10-10  
**Kernel:** Linux `7.2.8 #2 SMP PREEMPT_DYNAMIC` (NFTables enabled)  
**Toolchain:** glibc `2.44`, binutils `2.47`, GCC `16.2.0`, Rust `1.98.1`  
**Package Manager:** Portadora `0.2.0` (Upgraded from `0.1.0` via verified self-upgrade)  
**Rootfs Package Count:** 56 managed packages (`portadora verify`: All managed files verified)

---

## 1. Executive Summary

Milestone 5 achieves the complete transformation of Portadora into a resilient, cryptographic-grade package management and secure update ecosystem for BlazeOS Native, without incurring technical debt or compromising architectural invariants:

- **The Update Framework (TUF) Specification Engine**:
  - Full RFC 8785 canonical JSON serialization (JCS) and Ed25519 cryptographic signature verification across four-role TUF hierarchy (`root`, `timestamp`, `snapshot`, `targets`).
  - Monotonic version enforcement preventing downgrade/rollback attacks.
  - Expiry and freeze attack detection preventing replay of stale repository states.
  - Seamless dual-signed root key rotation, advancing the system's trust anchor from Root v1 to Root v2 without client disruption.
- **Durable Write-Ahead Transaction Journal**:
  - All package installations, upgrades, and removals are mediated by an atomic write-ahead journal (`/var/lib/portadora/journal`).
  - Strict staging area extraction with individual file `fsync` and parent directory `fsync` barriers before committing.
  - Crash recovery engine (`portadora recover` / automatic startup hook) capable of detecting incomplete transactions and rolling back or rolling forward cleanly, preventing partial writes and dangling state.
- **Topological Dependency & Conflict Resolver**:
  - Graph-based dependency DAG resolution using depth-first search cycle detection.
  - Automatic detection and rejection of cyclic dependencies (`A -> B -> A`).
  - Conflict detection rejecting packages claiming identical file paths or conflicting package relationships before initiating disk writes.
  - Semantic versioning comparison guaranteeing selection of latest compatible package releases.
- **In-Flight Self-Upgrade Protocol**:
  - Safe replacement of the running package manager binary (`portadora upgrade portadora`).
  - Staging, journaled file replacement, and atomic swap tested live inside QEMU, upgrading Portadora from version `0.1.0` to `0.2.0` with 100% database and filesystem consistency.
- **Resilient Remote Fetching**:
  - HTTP Range requests supporting resumable package downloads.
  - Streaming SHA-256 hash computation and length verification rejecting corrupt or tampered payloads before staging.
- **Network & Firewall Hardening (RFC 4890 & OpenSSH)**:
  - NFTables firewall ruleset refined to conform strictly to RFC 4890 for ICMPv6 (Router Solicitation/Advertisement, Neighbor Solicitation/Advertisement with `hoplimit 255`, and rate-limited Echo Request).
  - OpenSSH inbound connectivity (`tcp dport 22 accept`) validated with real Ed25519 key authentication over forwarded port 2222, while strictly enforcing default-disabled systemd presets across reboots.

---

## 2. Milestone 5 Package & Component Matrix

| Component / Package | Version | Provides / Purpose | Status |
|---|---|---|---|
| `portadora-core` | `0.2.0` | TUF verifier (RFC 8785 + Ed25519), write-ahead journal, dependency DAG resolver, HTTP downloader | Verified |
| `portadora` CLI | `0.2.0` | Full CLI suite (`update`, `search`, `info`, `install`, `upgrade`, `remove`, `list`, `verify`, `history`, `recover`) | Verified |
| `nano` | `8.1-1` | GNU nano terminal editor (`/usr/bin/nano`), installed remotely via TUF repo | Verified |
| `repo-server.py` | `1.0.0` | Reference TUF repository generator, signer, key rotator, HTTP range server, and test fixture generator | Verified |
| `nftables.conf` | `0.2.0` | RFC 4890 ICMPv6 filtering, drop input/forward, controlled SSH port 22 | Verified |
| `blaze-network-config` | `0.1.0-2` | Networkd + resolved configuration with `disable sshd` preset intact | Verified |

---

## 3. Acceptance Test Results Matrix

All 15 verification scenarios were executed in an end-to-end automated QEMU harness (`tools/test-qemu-stage5-portadora.py`) with full console capture.

| ID | Test Scenario | Verified Behavior | Exit Code | Result |
|---|---|---|---|---|
| **M5-01** | TUF Repository Sync | `portadora update` verified `root.json`, `timestamp.json`, `snapshot.json`, and `targets.json` using Ed25519 keys; synced 74 packages into local state cache | 0 | **PASS** |
| **M5-02** | Repository Search & Info | `portadora search nano` and `portadora info nano` resolved package metadata, version `8.1`, size, hashes, and dependencies from `targets.json` | 0 | **PASS** |
| **M5-03** | Remote Package Installation | `portadora install nano` downloaded `.blz` with HTTP stream SHA-256 verification, applied write-ahead journal, registered in SQLite DB, and `/usr/bin/nano --version` returned GNU nano 8.1 | 0 | **PASS** |
| **M5-04** | Negative: Tampered Package | `portadora install corrupt-pkg` detected SHA-256 mismatch during download; aborted prior to journal commit; zero untracked files or DB entries created | 0 | **PASS** |
| **M5-05** | Negative: Expired & Rollback Metadata | Test fixtures with expired timestamps rejected with `SecurityError: Expired metadata`; rollback metadata rejected with `SecurityError: Rollback detected` | 0 | **PASS** |
| **M5-06** | Dependency Cycles & Conflicts | `cycle-a` / `cycle-b` rejected with `Dependency cycle detected`; `conflict-nano` rejected with `Conflict: file already owned by nano` without modifying disk | 0 | **PASS** |
| **M5-07** | Crash Recovery (`portadora recover`) | Injected interrupted transaction journal with staged files; `portadora recover` executed rollback of incomplete transaction, removing staging and maintaining DB consistency | 0 | **PASS** |
| **M5-08** | In-Flight Self-Upgrade | `portadora upgrade portadora` upgraded binary from `0.1.0` to `0.2.0`; journaled swap executed cleanly; `portadora --version` confirmed `portadora 0.2.0` | 0 | **PASS** |
| **M5-09** | Pre-Reboot Package Integrity | `portadora verify` checked SHA-256 checksums, permissions, and paths for all 56 installed packages; reported `All managed files verified.` | 0 | **PASS** |
| **M5-10** | Graceful Reboot & Post-Reboot Health | Executed `systemctl reboot`; VM rebooted cleanly; verified systemd units healthy; `/usr/bin/nano --version` executed cleanly | 0 | **PASS** |
| **M5-11** | TUF Root Key Rotation | Repository rotated root key v1 -> v2 dual-signed; client `portadora update` validated dual signatures, transitioned trust anchor to v2, and updated metadata | 0 | **PASS** |
| **M5-12** | Hardened IPv6 RFC 4890 Firewall | `nft list ruleset` confirmed RFC 4890 rules (hoplimit 255 RA/ND, rate-limited echo); `ping -6 -c 2 ::1` succeeded with 0% loss | 0 | **PASS** |
| **M5-13** | Authenticated SSH Remote Session | Key injected into `/root/.ssh/authorized_keys`, `sshd` started on-demand, authenticated SSH session over port 2222 executed remote commands; `sshd` stopped and confirmed disabled on boot | 0 | **PASS** |
| **M5-14** | Transaction History & Audit Trail | `portadora history` confirmed immutable audit log with timestamps, actions (`INSTALL`, `UPGRADE`), package names, and versions | 0 | **PASS** |
| **M5-15** | Post-Test System Integrity | Post-test `portadora verify` confirmed 0 corrupted files across all 56 packages; system powered off cleanly via `systemctl poweroff` | 0 | **PASS** |

---

## 4. Test Execution Log Highlights

From `reports/milestone-5/m5_test_output.log`:
- **Repository Setup**: Initialized TUF repo at `http://10.0.2.2:8080/repo` with 74 indexed packages.
- **TUF Verification**:
  ```text
  [TUF] Loading cached metadata...
  [TUF] Loaded root version 1
  [TUF] Root key rotation: updated to root version 2
  [TUF] Verification successful for role targets version 1
  ```
- **Portadora Remote Install**:
  ```text
  Downloading nano-8.1-1.x86_64.blz...
  Verified SHA-256 checksum for nano-8.1-1.x86_64.blz
  Beginning transaction: INSTALL nano 8.1-1
  Staging 35 files...
  Committing transaction to filesystem with fsync barriers...
  Transaction committed. Recorded in SQLite DB.
  /usr/bin/nano --version => GNU nano, version 8.1
  ```
- **Self-Upgrade**:
  ```text
  Upgrading portadora: 0.1.0-1 -> 0.2.0-1
  Transaction committed.
  portadora --version => portadora 0.2.0
  ```
- **Authenticated SSH**:
  ```text
  SSH authentication successful using id_ed25519.
  Remote command output: Linux blaze 7.2.8 #2 SMP PREEMPT_DYNAMIC
  GNU nano, version 8.1
  Service sshd stopped. Preset: disabled.
  ```

---

## 5. Architectural Invariants Status

1. **Deterministic State**: No package state exists outside `/var/lib/portadora/portadora.db` and `/var/lib/portadora/metadata/`.
2. **Cryptographic Integrity**: No binary or metadata is applied without valid Ed25519 signatures and SHA-256 verification.
3. **Power-Failure Resilience**: Write-ahead journal with strict file and directory `fsync` barriers prevents half-installed states.
4. **Security by Default**: Zero unexpected open ports; `sshd` remains inactive by default; firewall strictly drops unauthorized ingress traffic.
