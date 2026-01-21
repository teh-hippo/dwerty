# Dvorak + Qwerty Shortcuts for Keychron V6 Max (Windows-first)

_Last updated: January 2026_

Firmware keymap for the Keychron V6 Max (ANSI knob) that types **Dvorak** while keeping **Qwerty-position shortcuts**. The OS stays US Qwerty. Windows behavior is the priority; macOS support is included where it is easy.

## Features

| Feature | Description |
|---------|-------------|
| **Dwerty typing** | Dvorak layout with QWERTY-position shortcuts (Ctrl+C/V/Z work as expected) |
| **QWERTY toggle** | **Fn + Caps Lock** switches to standard QWERTY layout (persists across power cycles) |
| **Visual indicator** | Tab key glows **cyan** when QWERTY mode is active |
| **6 layers** | MAC_BASE, MAC_FN, WIN_BASE, WIN_FN, WIN_QWERTY, WIN_QWERTY_FN |
| **VIA support** | Full VIA compatibility for visual key remapping and lighting control |
| **RGB lighting** | All stock lighting effects preserved with Fn-layer controls |

## Quick Start

```bash
# 1. Setup QMK (Keychron fork with V6 Max support)
./scripts/setup_qmk.sh

# 2. Build firmware
QMK_DIR=~/qmk_keychron ./scripts/build.sh --artifacts

# 3. Flash (see Flashing section below)
```

## Keyboard Shortcuts

### Layout Toggle
| Combo | Action |
|-------|--------|
| **Fn + Caps Lock** | Toggle between Dwerty ↔ QWERTY (saved to EEPROM) |

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
- **QWERTY mode**: Standard QWERTY layout (toggle with Fn + Caps Lock)
- **Shortcut remapping**: Windows uses Ctrl/Alt/GUI; macOS uses Command only
- **Persistence**: Layout choice saved to EEPROM (survives power cycles)

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
- Remap any key
- Adjust lighting (brightness, effects, color, speed)
- Changes apply instantly (no reflash needed)

## Build Prerequisites

- QMK toolchain installed (QMK CLI or `make`)
- QMK tree with `keychron/v6_max` support (Keychron fork)

### WSL/Ubuntu dependency install (one-time)

```bash
python3 -m pip install --user qmk
sudo apt-get update
sudo apt-get install -y gcc-arm-none-eabi dfu-util
```

## Building

```bash
# Clone Keychron QMK fork (one-time)
./scripts/setup_qmk.sh

# Install keymap and build
QMK_DIR=~/qmk_keychron ./scripts/install_keymap.sh
QMK_DIR=~/qmk_keychron ./scripts/build.sh --artifacts
```

Output: `build/keychron_v6_max_ansi_encoder_dvorak_qwerty.bin`

## Flashing

### Option 1: QMK Toolbox (Windows/macOS GUI)

1. Build: `QMK_DIR=~/qmk_keychron ./scripts/build.sh --artifacts`
2. Open QMK Toolbox and load `build/keychron_v6_max_ansi_encoder_dvorak_qwerty.bin`
3. Put keyboard in bootloader mode: **hold Esc while plugging in USB**
4. Click **Flash**

### Option 2: WSL with USB Passthrough (Recommended for WSL users)

1. Install usbipd-win (Windows Admin PowerShell):

   ```powershell
   winget install usbipd
   ```

2. Put keyboard in bootloader mode: **hold Esc while plugging in USB**

3. Find and attach to WSL (Windows Admin PowerShell):

   ```powershell
   usbipd list                           # Find BUSID for STM32 BOOTLOADER
   usbipd bind --busid <BUSID>
   usbipd attach --wsl --busid <BUSID>
   ```

4. Flash from WSL:

   ```bash
   sudo dfu-util -a 0 -d 0483:df11 -s 0x08000000:leave -D ~/dwerty/build/keychron_v6_max_ansi_encoder_dvorak_qwerty.bin
   ```

5. Detach when done:

   ```powershell
   usbipd detach --busid <BUSID>
   ```

### Option 3: Copy to Windows

1. Build in WSL: `QMK_DIR=~/qmk_keychron ./scripts/build.sh --artifacts`
2. Copy `build/*.bin` to Windows
3. Flash using Keychron Launcher or QMK Toolbox

## Backup / Rollback

Download the official V6 Max firmware from Keychron's firmware page and flash it with Keychron Launcher or QMK Toolbox.

## Testing & Linting

```bash
./scripts/test.sh    # Run unit tests
./scripts/lint.sh    # Run all linters (Python, Shell, C)
```

## Podman Build (Optional)

Build firmware in a container without installing QMK on host:

```bash
./scripts/build.sh --podman
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
