# Milestone 9 Final Interactive Acceptance

Date: 2026-10-13

## Regression found and fixed

The first manual boot exposed a real regression: `getty@tty1` entered its
start limit because the `blaze` account existed in `/etc/passwd` but had no
matching `/etc/shadow` entry. PAM reported `Authentication service cannot
retrieve authentication info`, so Niri and Noctalia never started.

The disk assembler now treats the root and blaze shadow records as idempotent
upserts. The base filesystem recipe also declares the locked blaze record so
later assembly can safely assign the configured password hash.

## Acceptance evidence

- The corrected image reached the Noctalia onboarding screen through tty1
  autologin.
- QEMU VirtIO Tablet was registered as `/dev/input/event1`.
- Injected absolute motion and left-button events produced 96 bytes of raw
  Linux input-event data on `/dev/input/event1`.
- Clicking Noctalia's `Get Started` button closed onboarding and exposed the
  live panel and desktop.
- Clicking the panel launcher opened the application search surface with
  keyboard focus.
- Incorrect root credentials were rejected by PAM.
- Correct root credentials were accepted through `su`.
- The `blaze` user successfully elevated through `sudo`.
- Unprivileged Portadora mutation was rejected with actionable guidance.
- Privileged Fastfetch installation, `portadora verify`, and Fastfetch
  execution all completed successfully.

## Artifacts

- `m9_privilege_and_input_acceptance.log`
- `m9_final_ui_before.png`
- `m9_final_ui_after.png`
- `m9_final_ui_launcher.png`

The active validated disk is `build/blaze-disk-b11.raw`. The prior image is
retained locally as `build/blaze-disk-b11.pre-m9-final.raw` for recovery and is
excluded from version control with the other build artifacts.
