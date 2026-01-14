# Evaluation and Decision

## Problem statement (Windows first)
We want firmware-level Dvorak typing with Qwerty-position shortcuts ("Dvorak - QWERTY Command" behavior) while the OS remains US Qwerty. Windows is the priority target; macOS support should be included when it is low effort.

## Manufacturer guidance (Keychron)
- Keychron recommends the Keychron Launcher for firmware updates and remapping, and provides V6 Max firmware plus VIA JSON downloads on its support pages.
- The Keychron Launcher is a web app that supports remapping, macros, and firmware flashing for QMK/ZMK keyboards, and requires a wired USB connection.

References:
- https://www.keychron.com/pages/firmware-and-json-files-of-the-keychron-qmk-keyboards
- https://www.keychron.com/blogs/news/now-you-can-use-keychron-launcher-to-customize-your-keyboard
- https://www.keychron.com/pages/keychron-v6-max-firmware-and-json-files

## Options considered (with gaps)

### Option 1: Keychron Launcher only (no custom firmware)
Pros
- Official tooling, UI based, no local build required.

Cons
- Cannot implement conditional Dvorak + Qwerty shortcuts at the firmware level.
- No control over custom modifier-dependent remapping logic.

Verdict: Not sufficient for Dvorak-Qwerty-Command behavior.

### Option 2: VIA only (stock firmware)
Pros
- UI based editing after deployment.

Cons
- VIA remaps keys but does not provide conditional "when Ctrl/Alt/GUI is held" remap logic.
- Same limitation as Launcher: cannot implement the macOS Dvorak-Qwerty-Command behavior in firmware.

Verdict: Not sufficient alone.

### Option 3: QMK upstream (qmk/qmk_firmware)
Pros
- Most current QMK features, fixes, and community support.

Cons
- As of January 2026, upstream does not include Keychron V6 Max definitions.
- Requires a full keyboard port (wireless, MCU, matrix, encoder, lighting) which is high effort and high risk.

Verdict: Not viable until upstream supports V6 Max.

Reference:
- https://raw.githubusercontent.com/qmk/qmk_firmware/master/keyboards/keychron/v6_max/info.json

### Option 4: QMK Keychron fork (Keychron/qmk_firmware, wireless_playground)
Pros
- Official Keychron source that includes V6 Max definitions.
- Preserves stock behavior and hardware features (encoder, lighting, wireless).

Cons
- Vendor fork can lag upstream QMK updates.
- Update cadence depends on Keychron.

Verdict: Best practical option today.

Reference:
- https://raw.githubusercontent.com/Keychron/qmk_firmware/wireless_playground/keyboards/keychron/v6_max/info.json

### Option 5: TMK
Pros
- Simple and stable for classic AVR boards.

Cons
- No official V6 Max support; significant porting required.
- QMK already extends TMK with modern features and MCU support.

Verdict: Not appropriate for V6 Max.

Reference:
- https://docs.qmk.fm/#/faq_general?id=what-is-qmk

### Option 6: ZMK or Vial
Pros
- ZMK supports wireless-first devices; Vial offers a polished UI.

Cons
- No official V6 Max support or vendor guidance for these stacks.
- Would require a fork or port, and risk losing Keychron-specific features.

Verdict: Not recommended.

## Decision
- Base firmware on the Keychron QMK fork until upstream adds V6 Max.
- Implement Dvorak typing in firmware with Qwerty-position shortcuts when modifiers are held.
- Enable UI editing after deployment via VIA, and keep Keychron Launcher compatibility.
- Maintain stock encoder, lighting, and media behavior.

## Update and rollback
- Update QMK via `scripts/update_qmk.sh` (stays on current branch unless `QMK_BRANCH` is set).
- Roll back using Keychron-provided V6 Max firmware via Keychron Launcher (preferred) or QMK Toolbox.

## Gaps identified in the current repo
- No explicit evaluation of TMK, VIA-only, or Keychron Launcher-only approaches.
- No integration tests or CI workflow.
- No explicit rollback path in docs.
- macOS behavior not defined relative to "Dvorak - QWERTY Command".

## Fix plan
- Update firmware to mirror Windows-first Dvorak-Qwerty behavior and add Mac Command-only behavior.
- Add VIA support for UI editing and document Keychron Launcher usage.
- Add integration test coverage (host simulation + QMK build check).
- Add GitHub Actions to run unit/integration tests.
