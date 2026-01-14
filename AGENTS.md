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

## Target constraints
- Target keyboard: Keychron V6 Max (ANSI knob assumed unless user says ISO/JIS).
- Prefer upstream QMK when it supports V6 Max; otherwise use Keychron QMK fork `Keychron/qmk_firmware` on `wireless_playground` (see `EVALUATION.md`).
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
