# Dvorak + Qwerty Shortcuts for Keychron V6 Max

Firmware keymap for the Keychron V6 Max (ANSI knob) that types **Dvorak** while keeping **Qwerty-position shortcuts** (e.g., `Ctrl+C` is still on the physical Qwerty C key).

## What this does
- Dvorak typing at the firmware level (no OS layout changes required).
- Qwerty-position shortcuts when **Ctrl/Alt/GUI** is held.
- Maintains stock Keychron media keys and encoder (volume on base, RGB on Fn).
- Supports both Mac and Windows base layers (hardware toggle compatible).

## Implementation notes
- Shortcut remap is active only on base layers and releases cleanly even if modifiers are released first.
- Mod detection uses QMK modifier masks (Ctrl/Alt/GUI); Shift alone does not trigger remaps.

## Requirements
- QMK toolchain installed (QMK CLI or the `make`-based toolchain).
- QMK codebase with `keychron/v6_max` support. See `APPROACH.md`.

## Setup
1. Clone a QMK tree that supports V6 Max (recommended defaults shown):
   ```bash
   ./scripts/setup_qmk.sh
   ```

   This defaults to the Keychron fork (`Keychron/qmk_firmware`, `wireless_playground`). If you want to try upstream QMK:
   ```bash
   ./scripts/setup_qmk.sh --upstream
   ```

2. Copy the keymap into the QMK tree:
   ```bash
   QMK_DIR=~/qmk_firmware ./scripts/install_keymap.sh
   ```

   `QMK_DIR` defaults to `~/qmk_firmware` if not set.

3. Build the firmware:
   ```bash
   QMK_DIR=~/qmk_firmware ./scripts/build.sh
   ```

## Flashing to the keyboard
- Put the keyboard in **Cable mode** and enter bootloader mode by holding **Esc** while plugging in.
- Then flash using QMK CLI or `make`:
  ```bash
  QMK_DIR=~/qmk_firmware ./scripts/flash.sh
  ```

If you prefer QMK Toolbox, you can compile first (step 3) and then flash the produced `.bin` from the QMK build output.

## Tests
Run the unit tests that verify the shortcut remap table:
```bash
./scripts/test.sh
```

## Customizing
- **Enable Shift-only shortcuts:** edit `SHORTCUT_MOD_MASK` in
  `keymaps/keychron/v6_max/ansi_encoder/keymaps/dvorak_qwerty/keymap.c`.
- **ISO/JIS layouts:** this repo assumes ANSI knob (`ansi_encoder`). For ISO/JIS,
  mirror this keymap into the correct directory (`iso_encoder` or other variants).
- **UI editing later:** planned via VIA/Keychron Launcher JSON once the base keymap is stable.

## Layout notes
- Dvorak base layer follows the standard US Dvorak layout, including bracket placement.
- Qwerty shortcut remap only applies on **base layers** and only when Ctrl/Alt/GUI is held.

## References
- QMK setup/build docs: https://docs.qmk.fm/#/newbs_getting_started and https://docs.qmk.fm/#/getting_started_make_guide
- Keychron V6 Max QMK fork: https://github.com/Keychron/qmk_firmware
- Keychron flashing/reset guide: https://www.keychron.com/pages/how-to-factory-reset-or-flash-firmware-for-your-keychron-qmk-via-enabled-keyboard
