# Milestone 10 Phase C.1 — TUF Client-Chain Hardening

Date: 2026-10-14

## Outcome

Phase C.1 passed. Portadora 0.2.0-7 now refreshes and verifies repository
metadata before every remote search, install or upgrade; performs root rotation
one numbered version at a time; counts unique signing keys; enforces declared
metadata length and exact version; and refuses package downgrades. The final
Live ISO completed positive and hostile-repository acceptance in QEMU.

## Security fixes

- Removed the path that returned cached `targets.json` without checking its
  signature, expiry or snapshot binding.
- Root updates must advance by exactly one version and every intermediate
  `<version>.root.json` must be available and satisfy both old and new root
  thresholds. One run is limited to 32 rotations.
- Duplicate signatures from one key no longer count more than once toward a
  threshold.
- Snapshot and targets byte lengths and versions must exactly match the parent
  metadata, in addition to SHA-256 verification.
- Verified metadata and the trusted root are replaced atomically and synced to
  disk.
- Legacy root metadata without `consistent_snapshot` remains signature
  compatible; new repositories explicitly emit the field.
- `search` now accepts `--repo-url`, consistently with update/install/upgrade.
- Upgrade selection compares version and release, selects one newest candidate
  per installed package and never treats an older version as an upgrade.
- Repository private-key files are mode `0600`; the old deliberate corrupt-hash
  production indexing behavior was removed.
- Repository metadata and client status now identify TUF specification 1.0.36.

## Host and adversarial tests

| Scenario | Expected result | Result |
| --- | --- | --- |
| Root v1 to dual-signed v2 | Fetch `2.root.json`, verify both thresholds | Pass |
| Root v1 directly to v3 | Reject non-sequential rotation | Pass |
| Missing `2.root.json` | Stop without changing trusted root | Pass |
| Same key duplicated against threshold 2 | Count once and reject | Pass |
| Tampered targets bytes | Reject length/hash mismatch | Pass |
| Forged cached targets | Refresh from repository; never expose forged entry | Pass |
| Expired timestamp | Reject freeze metadata | Pass |
| Timestamp version rollback | Reject rollback | Pass |
| Older package with higher release | Never classify as an upgrade | Pass |
| Multiple versions of one package | Select only the newest eligible candidate | Pass |

## Final Live ISO VM acceptance

- Artifact: `build/iso/BlazeOS-Native-m10-phase-c1-x86_64.iso`
- SHA-256:
  `0f53d057c958f438420862ccc7b2fc70de35adbe869020c19f84094b6c6cef29`
- ISO checksum sidecar: pass.
- Live boot: systemd returned `running`; final failed-unit list was empty;
  networkd, nftables and seatd remained active.
- Root rotation: bundled legacy v1 root successfully advanced to v2 through
  `2.root.json` and persisted the new trust anchor.
- Remote update: pass, TUF 1.0.36 verification reported.
- Remote search with URL override: Fastfetch 2.69.0-1 found; pass.
- Remote install: `niri-session-assets` 1.0.0-1 downloaded, installed and all
  managed files verified; pass.
- Upgrade dry run: only genuinely newer `libseccomp` and `linux-blaze`
  candidates remained. Earlier glibc, display-info, kernel and Portadora
  downgrades were eliminated.
- Expired and rollback endpoints were both rejected inside the VM.

The serial direct-kernel harness briefly exhausted the ttyS0 getty restart
counter during repeated automated logins. Resetting that test-only failed state
returned the system to `running`; the package operations and services remained
healthy. The separate graphical/tty readiness item recorded in B.4 remains a
hardware-compatibility follow-up.

## Verification

- `cargo test --workspace`: pass (12 tests).
- Portadora/TUF unit and integration tests: pass (six tests).
- `python3 -m py_compile tools/repo-server.py`: pass.
- `git diff --check`: pass.
- ISO `SHA256SUMS`: pass.
- Four existing Portadora-Core compiler warnings outside the changed security
  paths remain scheduled for cleanup; they do not affect test results.

## Current-source baseline

- TUF stable specification 1.0.36:
  <https://github.com/theupdateframework/specification/releases/tag/v1.0.36>
- TUF root update workflow and intermediate-root requirement:
  <https://theupdateframework.github.io/specification/latest/>
- TUF project and conformance implementations:
  <https://github.com/theupdateframework>

## Next phase

Phase C.2 will separate offline root/targets signing from online timestamp
publication, exclude test fixtures from production channels, define stable and
staging layouts, and generate deterministic release manifests without keeping
production root keys on the repository host.
