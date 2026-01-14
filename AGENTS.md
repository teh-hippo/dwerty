# AGENTS.md

## Purpose
This repo ships a firmware keymap for the Keychron V6 Max that implements Dvorak typing with Qwerty-position shortcuts (macOS-style \"Dvorak - QWERTY Command\"). Windows behavior is the priority; macOS support should be kept when it is low effort. Agents must keep changes small, tested, and well-documented.

## Operating rules
- Work in small, reviewable steps. Prefer tidy diffs and minimal churn.
- Update `PLAN.md` after completing each step and keep status accurate.
- Update `README.md` whenever behavior, setup, or flashing steps change.
- Run available tests after each change when possible (`python -m unittest`).
- Keep scripts idempotent and safe; avoid destructive commands.
- After tests pass, commit and push to `origin`.
- Prefer Podman-based workflows for containerized builds; avoid Docker usage in docs or scripts.

## Project requirements (do not regress)
- Target keyboard: Keychron V6 Max (ANSI knob assumed unless user says ISO/JIS).
- Firmware-level Dvorak with Qwerty-position shortcuts; OS remains US Qwerty.
- Windows-first behavior; macOS support only when low effort.
- Preserve full hardware parity (all keys, encoder, media, lighting effects).
- Support UI-based editing after flash (VIA and Keychron Launcher compatibility).
- Provide unit tests and integration tests (no-hardware when possible).
- Provide rollback instructions and WSL-first workflow + flashing guidance.
- Keep CI workflows for tests.
- Allow framework updates to latest versions when required.

## Approach and mindset
- Keep the tooling decision in `README.md` current; compare manufacturer recommendations vs tooling reality using primary sources.
- Prefer upstream QMK when it supports V6 Max; otherwise use Keychron QMK fork `Keychron/qmk_firmware` on `wireless_playground`.
- Use the layout macro from `keychron/v6_max/ansi_encoder` (`LAYOUT_ansi_109`).
- Maintain encoder (knob) and media key behavior from the stock keymap.
- Keep VIA enabled for post-flash UI editing and preserve Keychron Launcher compatibility.
- Keep the QMK repo clean; upgrade using `scripts/update_qmk.sh` and keep keymaps in this repo.
- Default update path stays on the current QMK branch unless `QMK_BRANCH` is set.

## Layout behavior
- Base layers are Dvorak (firmware-level).
- Assume the host OS remains in US Qwerty unless the user explicitly wants OS-level Dvorak.
- Windows-first: when Ctrl/Alt/GUI is held on Windows base layers, remap to Qwerty positions for shortcuts.
- macOS: default to Command-only (GUI) remap to mimic \"Dvorak - QWERTY Command\".
- Shift alone must NOT trigger Qwerty remap (unless user explicitly asks).
- Remap applies only to base layers.
- Always unregister remapped keys on release even if modifiers are released first.

## Files of record
- Keymap lives at `keymaps/keychron/v6_max/ansi_encoder/keymaps/dvorak_qwerty/`.
- Tests live in `tests/` and validate shortcut mappings.
- Scripts live in `scripts/` and handle install/build/flash scaffolding.

## Continuous improvement
- If assumptions are wrong (layout variant, OS expectations, shortcut behavior), update this file immediately with the corrected rule.
- If any manual step is error-prone, add a scripted helper and document it.
