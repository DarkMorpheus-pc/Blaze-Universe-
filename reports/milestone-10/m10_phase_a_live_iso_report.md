# Milestone 10 Phase A — Live ISO Foundation

Date: 2026-10-13

## Result

BlazeOS Native now builds as a bootable hybrid BIOS/UEFI Live ISO. The live
system uses an immutable SquashFS lower layer and a writable tmpfs OverlayFS
upper layer, then starts the existing systemd, Niri, and Noctalia desktop
without requiring a virtual hard disk.

## Produced artifact

- File: `build/iso/BlazeOS-Native-m10-phase-a-x86_64.iso`
- Size: 2,590,996,480 bytes
- SHA-256: `bed077ea9381f21e3b9c7f270e6f790c93aa5b5cdc4ce3ebcccacabb0fe3b4e2`
- SquashFS size: 2,572,312,576 bytes
- Volume label: `BLAZEOS_LIVE`

## Architecture

1. Limine loads Linux 7.2.9 and the Blaze initramfs from ISO9660 media.
2. The kernel command line selects live mode with `blaze.live=1`.
3. Initramfs discovers and mounts the ISO read-only from `/dev/sr0`.
4. `/blaze/rootfs.squashfs` is attached to `/dev/loop0` and mounted read-only.
5. A tmpfs supplies OverlayFS `upperdir` and `workdir`.
6. The merged writable root becomes `/` before systemd is executed.

## Acceptance results

- Direct kernel + ISO live-root boot: PASS
- ISO9660 media discovery: PASS
- SquashFS loop mount: PASS
- Writable tmpfs OverlayFS root: PASS
- Critical ownership and SUID checks: PASS
- Root write test on the ephemeral upper layer: PASS
- Niri + Noctalia graphical live session: PASS
- Limine 12.9.1 UEFI boot through OVMF: PASS
- Limine 12.9.1 legacy BIOS boot through SeaBIOS: PASS
- ISO SHA-256 verification: PASS

Observed live mounts:

```text
/dev/sr0   /run/live/media  iso9660  ro
/dev/loop0 /run/live/lower  squashfs ro
tmpfs      /run/live/cow    tmpfs    rw
overlay    /                overlay  rw
```

## Build entry point

Run `tools/build-live-iso.sh` after producing the Linux 7.2.9 kernel and
initramfs. The builder synchronizes matching kernel modules, constructs the
SquashFS image, creates a hybrid Limine ISO, and writes a sidecar SHA-256 file.

Phase A deliberately stops before disk installation. Partitioning, target
root deployment, bootloader installation, and the Solar Installer UI belong
to Milestone 10 Phase B.
