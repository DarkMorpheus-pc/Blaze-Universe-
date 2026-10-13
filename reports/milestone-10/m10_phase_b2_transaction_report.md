# Milestone 10 Phase B.2 — Transactional Installer

Date: 2026-10-13

## Outcome

`solar-installer apply` now deploys BlazeOS from the Live ISO to a whole-disk
target. The resulting disposable 24 GiB VirtIO disk booted successfully after
the ISO was removed, using both OVMF/UEFI and SeaBIOS/legacy BIOS.

## Safety boundary

- Requires root privileges and a real whole block device.
- Rejects partitions, read-only devices, mounted targets, targets below 16 GiB,
  and removable media unless explicitly allowed.
- Requires `--confirm-erase` to exactly match the canonical target path.
- Holds a non-blocking exclusive `flock` for the complete transaction.
- Verifies the live root against `SHA256SUMS` before the first destructive step.
- Uses cleanup guards to unmount ESP and root filesystems after success or error.
- The QEMU guest received only its disposable test disk; no host disk was
  exposed to the guest.

## Installed layout

1. 1 MiB GPT BIOS Boot partition (`21686148-6449-6e6f-744e-656564454649`).
2. 512 MiB FAT32 EFI System Partition (`BLAZE-EFI`).
3. Remaining space as ext4 Linux x86-64 root (`blaze-root`).

Limine 12.9.1 is installed into the BIOS Boot partition and the ESP contains
`BOOTX64.EFI`, `limine-bios.sys`, both configuration locations, Linux 7.2.9,
and its initramfs. The installed `/etc/fstab` uses filesystem UUIDs.

## Failure-path evidence

Two live-environment gaps were found without silently continuing:

1. Missing `blockdev` stopped before partitioning. Target sizing was replaced
   with the Linux `BLKGETSIZE64` ioctl, removing that runtime dependency.
2. Minimal-live udev did not drain its event queue. The transaction stopped
   after partition creation and before formatting. It now waits directly for
   all expected partition nodes with a bounded timeout.
3. A previously installed ESP was mounted by the rootfs's inherited `fstab`.
   Target validation correctly blocked the reinstall. The Live SquashFS now
   excludes `etc/fstab`; the installer writes a fresh UUID-based file only on
   the target system.

Both cases failed closed and were corrected before the successful deployment.

## Acceptance evidence

- Rust unit tests: 3 passed.
- Clippy with warnings denied: passed.
- Live root SHA-256:
  `fd3bbc8a328eef4716e8142f1ae51eb90e3d7ee730c0cb572a72c5a8fbd67d24`.
- Live ISO SHA-256:
  `d20216efdb143f088a680e51c0071a003701fe4c4bf6b66e0d039fe8f034cf7c`.
- Final Live ISO with an already-installed disk attached: passed; no live
  `fstab` was present, the ESP remained unmounted, and `/dev/vda` was eligible.
- Installed UEFI boot: passed; `/` was `/dev/vda3` ext4 and `/boot` was
  `/dev/vda2` vfat.
- Installed legacy BIOS boot: passed to the serial login prompt.

## Known follow-up

The installed system reaches the login prompt and desktop stack, but
`systemctl is-system-running` reports `degraded` because the existing
`nftables.service` fails. This is not an installer failure; it is the first
stability item for Phase B.3 alongside failure injection and recovery metadata.

Primary upstream references:

- https://github.com/Limine-Bootloader/Limine/blob/v12.x/USAGE.md
- https://github.com/Limine-Bootloader/Limine/blob/v12.x/CONFIG.md
- https://man7.org/linux/man-pages/man8/sfdisk.8.html
- https://github.com/plougher/squashfs-tools/blob/master/Documentation/4.7.5/USAGE-UNSQUASHFS.md
