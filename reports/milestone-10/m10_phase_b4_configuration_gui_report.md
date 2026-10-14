# Milestone 10 Phase B.4 — Configuration and Installer GUI Acceptance

Date: 2026-10-14

## Outcome

Phase B.4 passed. Solar Installer 0.4.0 now applies a validated answer file and
accepts the account password only through standard input. The Live ISO includes
a six-page Quickshell installer frontend, current timezone and keyboard data,
and a narrowly scoped live-only sudo rule. A configured installation completed
from the final ISO and the resulting disk booted cleanly through both UEFI and
legacy BIOS.

## Permanent fixes delivered

- Added strict validation for hostname, locale, timezone, keyboard layout,
  username, full name and password. Traversal, control characters, unsafe
  identity values and weak passwords are rejected before disk mutation.
- Kept the password out of JSON, process arguments, logs and the installed
  manifest. The CLI and GUI send it through a pipe; the in-memory buffer is
  cleared after use.
- Applied configuration with atomic file replacement and explicit `0644`
  permissions for public configuration such as `/etc/locale.conf`.
- Added locale generation, timezone linking, console/Niri keyboard selection,
  hostname configuration and account rename from the live `blaze` template.
- Corrected the renamed home tree to numeric UID/GID 1000. This avoids resolving
  the new account name against the live system's user database.
- Rewrote the `seatd` service account after the rename, preventing the desktop
  session from failing for non-default usernames.
- Removed `/etc/sudoers.d/solar-installer-live` from the installed target. The
  passwordless capability exists only on verified live media and permits only
  `/usr/bin/solar-installer`.
- Added a six-page Quickshell flow for welcome, target disk, region, identity,
  review and progress/result. Password input is masked and never serialized.
- Added IANA tzdata 2026e and kbd 2.10.0 packages to the live and installed
  roots.

## Negative and recovery-oriented validation

| User action | Expected result | Result |
| --- | --- | --- |
| Invalid hostname / traversal-like identity | Reject before target mutation | Pass |
| Weak password | Reject before target mutation | Pass |
| Missing or invalid locale/timezone/keymap | Reject against target resources | Pass |
| Valid answers with password on stdin | Complete all 9 installation steps | Pass |
| Reinstall onto an already partitioned test disk | Recreate layout deterministically | Pass |
| Live sudo rule checked in installed root | Rule absent after extraction/configuration | Pass |

## Final VM acceptance

- Artifact: `build/iso/BlazeOS-Native-m10-phase-b4-x86_64.iso`
- ISO SHA-256:
  `16db7d2b9bdf83382a8f0f651780a38b6127a9e7a533b00237252b48567c8626`
- ISO checksum sidecar: pass.
- Target: disposable 20 GiB virtio disk with GPT, BIOS Boot, 512 MiB ESP and
  ext4 root.
- Installer: all 9 steps completed; exit status 0.
- Installed identity: `morpheus` / `Morpheus Test`, hostname `blaze-test`.
- Locale and region: `LANG=tr_TR.UTF-8`, timezone `Europe/Istanbul`, UTC offset
  `+0300`; `/etc/locale.conf` is readable mode `0644`.
- Input data: `loadkeys from kbd 2.10.0`; requested Turkish keymap recorded.
- Account: UID 1000, home `/home/morpheus`, owner `morpheus:blaze`, write test
  passed.
- Installed manifest: root-only
  `/var/lib/solar-installer/install.json` records installer 0.4.0, configuration,
  source digest and recovery model but no password.
- UEFI boot: systemd `running`, no failed units, `seatd` active, Fastfetch
  2.69.0 starts, live sudo rule absent.
- Legacy BIOS boot: systemd `running`, no failed units, `seatd` active, locale,
  hostname and home write tests pass.
- Quickshell frontend: QML loads through its offscreen platform and reaches
  `Configuration Loaded`; the expected host-only missing installer executable
  does not affect the Live ISO. Niri + Noctalia was also visually reached with
  the final live stack.

## Host-side verification

- `cargo test -p solar-installer`: pass (six tests).
- `cargo clippy -p solar-installer --all-targets -- -D warnings`: pass.
- `cargo fmt -p solar-installer -- --check`: pass.
- `bash -n tools/build-live-iso.sh`: pass.
- `git diff --check`: pass.
- Workspace-wide formatting still reports pre-existing differences in Builder
  and Portadora sources outside this phase; those files were not rewritten.

## Known follow-up

With the exact QEMU virtio-GPU/GTK configuration, the DRM node can appear after
the conditional tty1 unit is evaluated. Manually starting `solar-session`
reaches Niri + Noctalia, so the graphics stack is functional, but automatic
graphical-session readiness should be made event-driven in the next hardware
compatibility phase. Headless, UEFI and BIOS installed-system paths are not
affected.

## Primary references

- systemd locale configuration:
  <https://www.freedesktop.org/software/systemd/man/latest/locale.conf.html>
- GNU C Library locale generation:
  <https://www.gnu.org/software/libc/manual/html_node/Locale-Names.html>
- Linux account management (`useradd`/`usermod` family):
  <https://man7.org/linux/man-pages/man8/usermod.8.html>
- IANA Time Zone Database releases:
  <https://www.iana.org/time-zones>
- Linux kbd releases:
  <https://www.kernel.org/pub/linux/utils/kbd/>
- Quickshell process API:
  <https://quickshell.org/docs/types/Quickshell.Io/Process/>
