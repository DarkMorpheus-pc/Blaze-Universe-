# Milestone 10 Phase B.3 — Recovery and Stability Acceptance

Date: 2026-10-13

## Outcome

Phase B.3 passed. Solar Installer 0.3.0 now exposes deterministic, hidden
failure-injection checkpoints and records an atomically replaced transaction
journal at `/run/solar-installer/transaction.json`. A failed install can be
restarted from the checksum-verified Live ISO without retaining mounts or
depending on partially written state.

The installed manifest records the installer version, verified SquashFS
SHA-256, transaction schema and the `restart-from-verified-source` recovery
model. The final disposable 20 GiB disk booted successfully through both UEFI
and legacy BIOS.

## Permanent fixes delivered

- Added failure checkpoints after source verification, partitioning,
  formatting, extraction and bootloader installation.
- Made transaction checkpoint replacement durable with file `sync_all`,
  atomic rename and parent-directory `sync_all`, following the durability
  requirements documented by `fsync(2)`.
- Enabled the kernel nftables features required by the shipped `inet` ruleset:
  `NF_TABLES_INET`, `NFT_CT`, `NFT_LIMIT` and `NFT_REJECT_INET`.
- Raised `linux-blaze` to release 4 and fixed the kernel package builder so its
  output is always rooted at the Blaze workspace rather than the kernel source
  working directory.
- Added a tty1 recovery-shell fallback and made graphical autologin conditional
  on `/dev/dri/card0`. DRM-less/headless systems use the serial console without
  triggering a getty restart loop or degrading systemd state.

## Failure-injection matrix

All cases used `build/solar-installer-b3.raw`; the target was checked for stale
mounts after every injected failure.

| Case | Expected durable state | Result |
| --- | --- | --- |
| Wrong erase confirmation | No partition-table mutation | Pass |
| `verified` | Source checksum verified, disk untouched | Pass |
| `partitioned` | GPT present, no new filesystems | Pass |
| `formatted` | FAT32/ext4 present, no retained mounts | Pass |
| `extracted` | Root extracted, cleanup guard unmounted target | Pass |
| Full rerun | Recreates target and reaches `complete` | Pass |

## Final VM acceptance

- Final ISO SHA-256:
  `0769fc40b6b5d96b35f11daa100d82c32d3ed848af90faffc03904232053442b`
- Final SquashFS SHA-256:
  `3aaf70dfcb949f5c739e4d11820997223ce07f526bbd0609f5dfe480fba33c83`
- ISO `SHA256SUMS`: every listed boot, installer and rootfs artifact passed.
- Live headless boot: systemd `running`, no failed units, nftables active,
  conditional tty1 result `success`, zero restarts.
- Installed UEFI boot: systemd `running`, no failed units, kernel 7.2.9,
  nftables active and `nft -c -f /etc/nftables.conf` successful.
- Installed legacy BIOS boot: systemd `running`, no failed units and nftables
  validation successful.
- Storage: `/dev/vda3` ext4 on `/`; `/dev/vda2` vfat on `/boot`.
- User path: `/home/blaze` is writable and owned by `blaze:blaze`; Fastfetch
  2.69.0 starts; DNS resolution succeeds.
- Graphical path: virtio GPU reaches Niri + Noctalia at 1280x800; virtio tablet
  is selected and pointer movement was injected through the QEMU monitor.
- Evidence: `m10_b3_final_gui_desktop.png`.

## Host-side verification

- `cargo test --workspace`: pass (six tests total).
- `cargo test -p solar-installer`: pass (three tests).
- `cargo clippy -p solar-installer --all-targets -- -D warnings`: pass.
- `cargo fmt -p solar-installer -- --check`: pass.
- Shell syntax and `git diff --check`: pass.

The workspace-wide formatting check still reports pre-existing formatting
differences outside Solar Installer. Workspace tests also retain four existing
Portadora warnings; neither was changed as part of this installer phase.

## Follow-up compatibility work

The boot journal reports non-fatal udev rule references for optional components
that are not yet packaged (`tss`, `i2c`, `adbusers`, `rfkill`, `sysctl`,
`nfsrahead`, and `set-wireless-regdom`). These do not create failed services or
block boot. They are recorded for the next hardware/driver compatibility pass,
where each rule will either gain its owning package/user or be omitted when the
feature is not installed.

## Primary references

- nftables command validation and ruleset loading:
  <https://netfilter.org/projects/nftables/manpage.html>
- Linux durability semantics for `fsync(2)` and directory entries:
  <https://man7.org/linux/man-pages/man2/fsync.2.html>
- systemd boot and failed-unit diagnostics:
  <https://wiki.freedesktop.org/www/Software/systemd/Debugging/>
