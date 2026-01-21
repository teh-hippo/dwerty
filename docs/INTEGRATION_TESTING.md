# Integration testing plan (no deps required by default)

## Goals
- Validate Dvorak typing + Qwerty-position shortcuts in firmware logic.
- Ensure Windows-first behavior and macOS Command-only behavior are preserved.
- Keep tests runnable without hardware or external dependencies by default.

## Current coverage (implemented)
1. **Simulation tests** (no hardware, no QMK toolchain)
   - Location: `tests/test_integration_simulation.py`
   - Focus: modifier triggers, base-layer-only enforcement, and release behavior.
   - Run: `./scripts/test.sh --integration`
   - Includes common Windows shortcut vectors and ensures unmapped keys pass through.

2. **Optional build gate** (requires QMK toolchain + network)
   - Script: `./scripts/test.sh --build`
   - Purpose: ensure keymap compiles against the chosen QMK tree.
   - Not part of default test run until dependencies are installed.

3. **Optional hardware-in-the-loop (HIL) smoke tests**
   - Use WSL + `usbipd-win` to attach the keyboard to WSL.
   - Flash the test build and validate shortcuts via manual UAT.
   - Automated UI checks can be added later (AutoHotkey/PowerShell) if needed.

## Manual UAT checklist (WSL-first)
1. Build firmware in WSL (`./scripts/build.sh`).
2. Put the keyboard in bootloader mode (hold **Esc** while plugging in via USB).
3. Attach USB to WSL using `usbipd-win` (see README for the exact commands).
4. Flash from WSL (`./scripts/flash.sh`).
5. Validate on Windows host:
   - Dvorak typing on base layer (OS stays US Qwerty).
   - Ctrl/Alt/Win shortcuts map to Qwerty positions.
   - Fn layers do not remap.
   - Encoder and media keys behave as stock.
6. Optional macOS sanity check (later): Command-only remap behavior.

## Notes
- Optional checks are documented but remain opt-in by default.
