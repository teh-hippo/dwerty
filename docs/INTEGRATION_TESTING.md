# Integration testing plan (no deps required by default)

## Goals
- Validate Dvorak typing + Qwerty-position shortcuts in firmware logic.
- Ensure Windows-first behavior and macOS Command-only behavior are preserved.
- Keep tests runnable without hardware or external dependencies by default.

## Current coverage (implemented)
1. **Simulation tests** (no hardware, no QMK toolchain)
   - Location: `tests/test_integration_simulation.py`
   - Focus: modifier triggers, base-layer-only enforcement, and release behavior.
   - Run: `./scripts/test_integration.sh`

## Planned expansion (still no deps by default)
2. **Shortcut vector table tests**
   - Expand integration tests to include common Windows shortcuts (e.g., Ctrl+C/V/X/Z/A/S/F) and macOS Command equivalents.
   - Verify Shift-only does not trigger remap and that non-base layers never remap.

3. **Optional build gate (requires QMK toolchain + network)**
   - Script: `./scripts/test_qmk_build.sh`
   - Purpose: ensure keymap compiles against the chosen QMK tree.
   - Not part of default test run until dependencies are installed.

4. **Optional hardware-in-the-loop (HIL) smoke tests**
   - Use WSL + `usbipd-win` to attach the keyboard to WSL.
   - Flash the test build and validate shortcuts via manual UAT.
   - Automated UI checks can be added later (AutoHotkey/PowerShell) if needed.

## Notes
- Phase 2 is intentionally a simulation to keep tests fast and dependency-free.
- Phases 3 and 4 are opt-in; they remain documented but disabled by default.
