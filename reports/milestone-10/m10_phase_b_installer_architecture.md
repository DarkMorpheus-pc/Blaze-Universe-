# Milestone 10 Phase B — Installer Architecture Baseline

Date: 2026-10-13

## Upstream review

- Limine 12.9.1 is the current signed stable release. BlazeOS pins the
  official binary archive SHA-256 and no longer depends on the host's older
  Limine installation.
- Calamares 3.4.2 is explicitly described upstream as a test release. The
  production UI integration will therefore target the stable 3.3 series or
  a SolarUI frontend over the same installer core; the storage engine will
  not depend on an experimental Calamares release.
- Current util-linux `sfdisk` documentation recommends exclusive device
  locking to avoid udev races and MiB-based/default placement for portable
  alignment. The transaction holds its own exclusive lock for its complete
  lifetime and uses GPT, explicit signature wiping, and named type GUIDs.

Primary references:

- https://github.com/Limine-Bootloader/Limine/releases/tag/v12.9.1
- https://calamares.codeberg.page/
- https://calamares.codeberg.page/calamares-3.3.14-is-out/
- https://man7.org/linux/man-pages/man8/sfdisk.8.html

## Implemented Phase B.1 foundation

The new `solar-installer` Rust crate provides a non-destructive storage
planner:

- discovers whole-disk candidates from `/sys/class/block`;
- excludes loop, RAM, device-mapper, optical, partition, read-only, mounted,
  and undersized targets;
- requires at least 16 GiB;
- validates that the live SquashFS source exists;
- emits a machine-readable versioned JSON plan;
- defines a 1 MiB BIOS Boot partition, a 512 MiB EFI System Partition, and a
  Linux x86-64 root partition;
- records the ordered deployment and verification transaction;
- performs no writes in `probe` or `plan` mode.

The host NVMe containing the active system was correctly reported as blocked.
A 20 GiB sparse regular-file fixture produced the expected plan without being
modified.

Phase B.2 implemented the privileged transaction executor and verified it on
a disposable QEMU disk. See `m10_phase_b2_transaction_report.md` for the
transaction, failure-path, UEFI, and legacy BIOS evidence.
