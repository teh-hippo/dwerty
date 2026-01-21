# Dvorak + Qwerty Shortcuts for Keychron V6 Max

Firmware keymap for the Keychron V6 Max (ANSI knob) that types **Dvorak** while keeping **Qwerty-position shortcuts**. The OS stays US Qwerty.

## Features

- **Dwerty typing**: Dvorak layout with QWERTY-position shortcuts (Ctrl+C/V/Z work as expected)
- **Layer cycling**: Fn + Z/X cycles layers and shows brief number-row indicator
- **Visual indicator**: Tab glows red (Dwerty), yellow (QWERTY), or blue (other layers)
- **6 layers**: MAC_BASE, MAC_FN, WIN_BASE, WIN_FN, WIN_QWERTY, WIN_QWERTY_FN
- **VIA support**: Full VIA compatibility for visual key remapping
- **RGB lighting**: All stock effects preserved with Fn-layer controls

## Quick Start

1. **Bootloader mode**: Hold Esc while plugging in USB
2. **Attach to WSL** (Windows Admin PowerShell):

   ```powershell
   usbipd list
   usbipd bind --busid <BUSID>
   usbipd attach --wsl --busid <BUSID>
   ```

3. **Build + flash**:

   ```bash
   ./scripts/firmware.sh
   ```

## Keyboard Shortcuts

**Layout Toggle**
- **Fn + Z/X**: Cycle layers (shows layer number briefly)
- **VIA: `LAYOUT_DVORAK`/`LAYOUT_QWERTY`**: Set default layer

**Fn Layer**
- Lighting controls: Tab (toggle), Q/A (effects), W/S (brightness), E/D (hue), R/F (saturation), T/G (speed)
- Encoder: Brightness up/down
- Connectivity: 1/2/3 (Bluetooth), 4 (2.4G), B (battery), N (N-key rollover)

## VIA Support

Use [usevia.app](https://usevia.app) in Chrome/Edge for visual key remapping:

1. **Settings** → enable **Show Design Tab**
2. **Design** tab → **Load** [`via/v6_max_ansi_encoder.json`](via/v6_max_ansi_encoder.json)
3. **Configure** tab → edit layers, assign `LAYOUT_DVORAK`/`LAYOUT_QWERTY`, remap keys, adjust lighting
