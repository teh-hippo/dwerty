# Dvorak + Qwerty Shortcuts for Keychron V6 Max

_Last updated: January 2026_

Firmware keymap for the Keychron V6 Max (ANSI knob) that types **Dvorak** while keeping **Qwerty-position shortcuts**. The OS stays US Qwerty. Windows-first with macOS support.

## Features

- **Dwerty typing**: Dvorak layout with QWERTY-position shortcuts (Ctrl+C/V/Z work as expected)
- **Layer cycling**: Fn + Z/X cycles layers and shows brief number-row indicator
- **Visual indicator**: Tab glows red (Dwerty), yellow (QWERTY), or blue (other layers)
- **6 layers**: MAC_BASE, MAC_FN, WIN_BASE, WIN_FN, WIN_QWERTY, WIN_QWERTY_FN
- **VIA support**: Full VIA compatibility for visual key remapping
- **RGB lighting**: All stock effects preserved with Fn-layer controls

## Quick Start (WSL + Podman)

1. **Bootloader mode**: Hold Esc while plugging in USB
2. **Attach to WSL** (Windows Admin PowerShell):

   ```powershell
   usbipd list                           # Find BUSID for STM32 BOOTLOADER
   usbipd bind --busid <BUSID>
   usbipd attach --wsl --busid <BUSID>
   ```

3. **Build + flash** (WSL):

   ```bash
   ./scripts/firmware.sh
   ```

## Commands

```bash
./scripts/firmware.sh         # build + flash (default)
./scripts/firmware.sh build   # build only
./scripts/firmware.sh flash   # flash only
./scripts/test.sh             # run tests
./scripts/lint.sh             # run linters
```

## Keyboard Shortcuts

**Layout Toggle**
- **Fn + Z/X**: Cycle layers (shows layer number briefly)
- **VIA: `LAYOUT_DVORAK`/`LAYOUT_QWERTY`**: Set default layer (saved to EEPROM)

**Lighting (Fn layer)**
- **Tab**: Toggle RGB | **Q/A**: Cycle effects | **W/S**: Brightness | **E/D**: Hue | **R/F**: Saturation | **T/G**: Speed
- **Encoder (Fn)**: Brightness up/down

**Connectivity (Fn layer)**
- **1/2/3**: Bluetooth host 1/2/3 | **4**: 2.4G wireless | **B**: Battery level | **N**: Toggle N-key rollover

## VIA Support

Use [usevia.app](https://usevia.app) in Chrome/Edge for visual key remapping:

1. **Settings** → enable **Show Design Tab**
2. **Design** tab → **Load** [`via/v6_max_ansi_encoder.json`](via/v6_max_ansi_encoder.json)
3. **Configure** tab → edit layers, assign `LAYOUT_DVORAK`/`LAYOUT_QWERTY`, remap keys, adjust lighting

## Backup / Rollback

Download official V6 Max firmware from [Keychron's firmware page](https://www.keychron.com/pages/keychron-v6-max-firmware-and-json-files) and flash with Keychron Launcher (Chrome/Edge/Opera) or QMK Toolbox.

## Customizing

- **Shortcut modifiers**: Edit `SHORTCUT_MOD_MASK_WIN`/`SHORTCUT_MOD_MASK_MAC` in [keymap.c](keymaps/keychron/v6_max/ansi_encoder/keymaps/dvorak_qwerty/keymap.c)
- **ISO/JIS layouts**: Mirror this keymap to `iso_encoder` or other variants

## WSL USB Detach

```powershell
usbipd detach --busid <BUSID>
```
