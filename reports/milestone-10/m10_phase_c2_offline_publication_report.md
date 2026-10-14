# Milestone 10 Phase C.2 — Offline Signing and Deterministic Publication

Date: 2026-10-14

## Outcome

Phase C.2 passed. Blaze Universe now has separate offline and online signing
boundaries, independent `stable` and `staging` trust roots, deterministic
release manifests, test-fixture exclusion for production, rollback-resistant
metadata versions and atomic channel activation. The Live ISO completed the
full remote-package and graphical-session acceptance matrix in QEMU.

## Security architecture

- Updated generated metadata and Portadora reporting to TUF 1.0.37.
- Root and targets private keys exist only in the offline key store.
- Snapshot and timestamp private keys exist only in the online key store.
- Stable and staging use distinct keys for every TUF role.
- Published trees contain no key files or private-key databases.
- Private key files require mode `0600`; private directories use `0700`.
- Every offline transfer is checked against a deterministic SHA-256 inventory
  before the online signer processes it.
- Repository versions cannot decrease. Reusing a version with different bytes
  is rejected; identical publication is idempotent.
- Publication is staged, synced to disk and activated by atomic rename with
  restoration of the prior channel on failure.
- `release-manifest.json` is signed by the channel snapshot key and both the
  manifest and detached signature are listed in `SHA256SUMS`.

## Channel policy

The stable repository excludes six deliberate hostile fixtures:

- `conflict-*`
- `corrupt-*`
- `cycle-*`
- `portadora-broken-*`

The final version-2 acceptance repositories contain 165 stable packages and
171 staging packages. A client bootstrapped with the stable root rejected the
staging timestamp with `ThresholdNotMet`, proving cryptographic channel
isolation rather than URL-only separation.

## Host acceptance

- Deterministic offline bundle generation: pass.
- Deterministic online publication: pass.
- Offline/online key-role separation: pass.
- Stable fixture exclusion and staging inclusion: pass.
- Tampered transfer rejection without modifying the live channel: pass.
- Metadata rollback rejection: pass.
- Detached release-manifest signature verification: pass.
- Full `SHA256SUMS` verification for 165 packages and metadata: pass.
- Independent TUF signature, threshold, expiry and canonicalization checks:
  pass.
- `cargo test --workspace`: 12 tests passed.

## Live ISO acceptance

- Artifact: `build/iso/BlazeOS-Native-m10-phase-c2-x86_64.iso`
- SHA-256: `74af2b42007fcd7a9cae5883afda2db29a38ae1ad1ef85f22b02836ea0258945`
- Hybrid UEFI boot: pass.
- Live media identity: Phase C.2 confirmed.
- System state: `running`; failed-unit list empty.
- Portadora 0.2.0-8 with TUF 1.0.37: pass.
- Remote stable update and Fastfetch search: pass.
- Deliberate broken package absent from stable search: pass.
- Remote `niri-session-assets` installation and managed-file verification:
  pass.
- Stable client rejected staging channel metadata: pass.
- Niri plus Noctalia/Solar shell process readiness: pass.

The test also closed the B.4 graphical readiness follow-up. A static
`ConditionPathExists=/dev/dri/card0` caused tty1 to be skipped permanently when
the DRM device appeared after initial unit evaluation. The condition was
removed, `virtio-gpu` is loaded during early boot, and the user profile now
performs a bounded DRM wait while preserving a text recovery shell.

## Reproducibility and operational boundary

The key material under `build/m10-c2-keys/` is disposable and ignored by Git.
The public release must use a fresh key ceremony on encrypted offline storage,
following `docs/release/tuf-publication.md`. Phase C.3 will add mirror failover,
full-system upgrade acceptance and publication to the selected public services.

## Current sources

- TUF stable specification 1.0.37:
  <https://github.com/theupdateframework/specification/blob/master/tuf-spec.md>
- TUF specification project and release process:
  <https://github.com/theupdateframework/specification>

## Next phase

Phase C.3 will implement ordered mirror failover, verify a complete system
upgrade across metadata versions, assemble final ISO/repository artifacts, and
exercise public release publication and recovery paths.
