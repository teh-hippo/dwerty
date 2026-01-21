# Dvorak + Qwerty Shortcuts for Keychron V6 Max (Windows-first)

_Last updated: January 2026_

Firmware keymap for the Keychron V6 Max (ANSI knob) that types **Dvorak** while keeping **Qwerty-position shortcuts**. The OS stays US Qwerty. Windows behavior is the priority; macOS support is included where it is easy.

## Features

| Feature | Description |
|---------|-------------|
| **Dwerty typing** | Dvorak layout with QWERTY-position shortcuts (Ctrl+C/V/Z work as expected) |
| **Layer cycling** | **Fn + Z / X** cycles layers down/up and shows a brief number-row indicator |
| **Visual indicator** | Tab key glows **cyan** when QWERTY mode is active |
| **6 layers** | MAC_BASE, MAC_FN, WIN_BASE, WIN_FN, WIN_QWERTY, WIN_QWERTY_FN |
| **VIA support** | Full VIA compatibility for visual key remapping and lighting control |
| **RGB lighting** | All stock lighting effects preserved with Fn-layer controls |

## Quick Start (WSL + Podman)

1. Put the keyboard in bootloader mode: **hold Esc while plugging in USB**
2. Attach the device to WSL (Windows Admin PowerShell):

   ```powershell
   usbipd list                           # Find BUSID for STM32 BOOTLOADER
   usbipd bind --busid <BUSID>
   usbipd attach --wsl --busid <BUSID>
   ```

3. One-line build + flash from WSL:

   ```bash
   ./scripts/firmware.sh podman
   ```

## Keyboard Shortcuts

### Layout Toggle
| Combo | Action |
|-------|--------|
| **Fn + Z** | Cycle to previous layer (shows layer number briefly) |
| **Fn + X** | Cycle to next layer (shows layer number briefly) |
| **VIA: `LAYOUT_DVORAK`** | Set default layer to Dwerty (saved to EEPROM) |
| **VIA: `LAYOUT_QWERTY`** | Set default layer to QWERTY (saved to EEPROM) |

### Lighting Controls (Fn layer)
| Combo | Action |
|-------|--------|
| **Fn + Tab** | Toggle RGB on/off |
| **Fn + Q / A** | Cycle effect forward / backward |
| **Fn + W / S** | Brightness up / down |
| **Fn + E / D** | Hue (color) up / down |
| **Fn + R / F** | Saturation up / down |
| **Fn + T / G** | Effect speed up / down |
| **Encoder (Fn)** | Brightness up / down |

### Connectivity (Fn layer)
| Combo | Action |
|-------|--------|
| **Fn + 1 / 2 / 3** | Bluetooth host 1 / 2 / 3 |
| **Fn + 4** | 2.4G wireless mode |
| **Fn + B** | Show battery level |
| **Fn + N** | Toggle N-key rollover |

## Behavior

- **Dwerty mode**: Dvorak typing with QWERTY-position shortcuts (Ctrl/Alt/GUI + key sends QWERTY position)
- **QWERTY mode**: Standard QWERTY layout (use `LAYOUT_QWERTY` in VIA or cycle to the QWERTY layer)
- **Shortcut remapping**: Windows uses Ctrl/Alt/GUI; macOS uses Command only
- **Layer cycling**: Fn + Z / X briefly blanks lighting, shows the layer index on the number row, then restores effects
- **Persistence**: Default layout choice saved to EEPROM (survives power cycles)

## VIA Support

This keymap is **VIA-enabled** for visual key remapping and lighting control.

### Setup

1. Open [usevia.app](https://usevia.app) in Chrome/Edge
2. Go to **Settings** (gear icon) → enable **Show Design Tab**
3. Go to **Design** tab → **Load Draft Definition**
4. Load [`via/v6_max_ansi_encoder.json`](via/v6_max_ansi_encoder.json) from this repo
5. Go to **Configure** tab — your keyboard should appear

### What you can do in VIA

- View and edit all 6 layers visually
- Assign `LAYOUT_DVORAK` / `LAYOUT_QWERTY` to any key for one-tap layout switching
- Remap any key
- Adjust lighting (brightness, effects, color, speed)
- Changes apply instantly (no reflash needed)

## Firmware Commands

The firmware script manages a repo-local cached QMK clone at `.cache/qmk_keychron`.
It **hard resets and cleans** that clone on every run, then pulls from Keychron’s
fork automatically. This keeps runs fast and deterministic.

### Podman (recommended)

```bash
./scripts/firmware.sh podman        # build + flash (default)
./scripts/firmware.sh podman build  # build only
./scripts/firmware.sh podman flash  # flash only
```

The Podman image is rebuilt only when [Containerfile](Containerfile) changes.
For `flash`/`all`, the script runs Podman via `sudo` when available to access USB.

### Local (power users)

```bash
./scripts/firmware.sh local        # build + flash (default)
./scripts/firmware.sh local build  # build only
./scripts/firmware.sh local flash  # flash only
```

Local mode requires a working QMK toolchain on your host.

## Backup / Rollback

Download the official V6 Max firmware from Keychron's firmware page and flash it with Keychron Launcher or QMK Toolbox.

## Testing & Linting

```bash
./scripts/test.sh    # Run unit tests
./scripts/lint.sh    # Run all linters (Python, Shell, C)
```

## WSL USB Detach (when done)

```powershell
usbipd detach --busid <BUSID>
```

## Customizing

- **Change shortcut modifier behavior:** edit `SHORTCUT_MOD_MASK_WIN` / `SHORTCUT_MOD_MASK_MAC` in
  `keymaps/keychron/v6_max/ansi_encoder/keymaps/dvorak_qwerty/keymap.c`.
- **ISO/JIS layouts:** this repo assumes ANSI knob (`ansi_encoder`). For ISO/JIS,
  mirror this keymap into the correct directory (`iso_encoder` or other variants).

## References

- [Keychron V6 Max Firmware](https://www.keychron.com/pages/keychron-v6-max-firmware-and-json-files)
- [VIA](https://usevia.app) / [VIA QMK Guide](https://caniusevia.com/docs/configuring_qmk/)
- [QMK Toolbox](https://github.com/qmk/qmk_toolbox)
- [usbipd-win (WSL USB)](https://learn.microsoft.com/windows/wsl/connect-usb)
