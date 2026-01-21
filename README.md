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
```

Linting runs automatically in CI before tests.

## VS Code Integration
This project is fully configured for VS Code with tasks, debuggers, and IntelliSense support for C, Python, and shell development.

### Recommended Extensions
Install recommended extensions via [`.vscode/extensions.json`](.vscode/extensions.json):
- **C/C++** (ms-vscode.cpptools) - QMK C code IntelliSense and formatting
- **Python** (ms-python.python) - Python debugging and testing
- **Ruff** (charliermarsh.ruff) - Python linting and formatting
- **ShellCheck** (timonwong.shellcheck) - Shell script analysis
- **Remote - WSL** (ms-vscode-remote.remote-wsl) - WSL integration
- **Remote - Containers** (ms-vscode-remote.remote-containers) - Dev Container support

VS Code will prompt you to install these when you open the project.

### Available Tasks
Access tasks via **Ctrl+Shift+P** → **Tasks: Run Task** (or **Ctrl+Shift+B** for the default build task):

**Build tasks:**
- **Build** - Standard QMK build (default build task)
- **Build (Podman)** - Build using Podman container
- **Build (Artifacts)** - Build and copy artifacts to `./build/`

**Test tasks:**
- **Test All** - Run all tests (default test task)
- **Test Unit** - Run unit tests only
- **Test Integration** - Run integration tests only
- **Test Build** - Run QMK build verification test

**Lint tasks:**
- **Lint** - Run all linters (Python, shell, C)

**Flash tasks:**
- **Flash** - Flash firmware to keyboard

**Setup tasks:**
- **Setup QMK** - Clone and set up QMK firmware
- **Update QMK** - Update QMK firmware to latest version

All tasks are configured in [`.vscode/tasks.json`](.vscode/tasks.json) with appropriate problem matchers for error detection.

### Debugging
Launch configurations are available for Python test debugging via [`.vscode/launch.json`](.vscode/launch.json):

- **Python: Debug Tests** - Debug all tests
- **Python: Debug Current Test File** - Debug the currently open test file
- **Python: Debug Unit Tests** - Debug unit tests only
- **Python: Debug Integration Tests** - Debug integration tests only

Press **F5** or use **Run → Start Debugging** to launch.

### C/C++ IntelliSense
QMK development IntelliSense is configured in [`.vscode/c_cpp_properties.json`](.vscode/c_cpp_properties.json):
- Include paths point to `~/qmk_firmware` (default QMK location)
- Configured for Linux/WSL GCC toolchain
- Defines `LAYOUT_ansi_109` and `VIA_ENABLE` for proper code completion

**Note:** IntelliSense paths assume QMK is installed at `~/qmk_firmware`. Run [`./scripts/setup_qmk.sh`](scripts/setup_qmk.sh) first if you haven't set up QMK yet.

### Settings
Linting and formatting are automatically applied via [`.vscode/settings.json`](.vscode/settings.json):
- Python files use Ruff for formatting and linting (format on save enabled)
- C files use `clang-format` with QMK style (uses [`.clang-format`](.clang-format))
- Shell scripts use ShellCheck for validation
- Python tests auto-discover in `tests/` directory

## Tests
All tests (unit + integration simulation):
```bash
./scripts/test.sh
```

Run tests with linting:
```bash
./scripts/test.sh --lint
```

Integration tests (no hardware required):
```bash
./scripts/test.sh --integration
```
These tests simulate modifier + layer behavior in a dummy firmware model. They do not emulate USB/Bluetooth timing, wireless stacks, or true hardware scans.

Integration test plan and expansion notes:
- See `docs/INTEGRATION_TESTING.md`.

Optional QMK build check (network + toolchain required):
```bash
./scripts/test.sh --build
```

## Podman workflows (preferred container path)
### Build the container image
```bash
./scripts/build.sh --podman
```

### Run a container shell
```bash
./scripts/podman_run.sh
```

From inside the container you can run:
```bash
./scripts/test.sh --build
./scripts/test.sh
```

## VS Code Dev Container (Podman backend)
This repo is pre-configured to use Podman for Dev Containers via [`.vscode/settings.json`](.vscode/settings.json):
```json
{
  "dev.containers.dockerPath": "podman",
  "dev.containers.dockerComposePath": "podman-compose"
}
```

### Setup
1. Install Podman and ensure it is configured for rootless use.
2. In VS Code, install the **Dev Containers** extension (recommended in [`.vscode/extensions.json`](.vscode/extensions.json)).
3. Open this repo and run: **Dev Containers: Reopen in Container**.
4. The container uses the same [`Containerfile`](Containerfile) as the Podman scripts.

## Keychron Launcher (web app) notes
- Launcher is the official web-based firmware path and expects a wired connection.
- Use Chrome, Edge, or Opera (latest) for best compatibility.
- Use QMK Toolbox or the CLI for custom `.bin` firmware.

## Customizing
- **Change shortcut modifier behavior:** edit `SHORTCUT_MOD_MASK_WIN` / `SHORTCUT_MOD_MASK_MAC` in
  `keymaps/keychron/v6_max/ansi_encoder/keymaps/dvorak_qwerty/keymap.c`.
- **ISO/JIS layouts:** this repo assumes ANSI knob (`ansi_encoder`). For ISO/JIS,
  mirror this keymap into the correct directory (`iso_encoder` or other variants).

## References
- Keychron Launcher: https://www.keychron.com/blogs/news/now-you-can-use-keychron-launcher-to-customize-your-keyboard
- Keychron firmware + JSON downloads: https://www.keychron.com/pages/keychron-v6-max-firmware-and-json-files
- Keychron QMK/VIA firmware index: https://www.keychron.com/pages/firmware-and-json-files-of-the-keychron-qmk-keyboards
- VIA QMK configuration guide: https://caniusevia.com/docs/configuring_qmk/
- Apple Dvorak - QWERTY Command layout: https://support.apple.com/en-lk/guide/mac-help/mchlp1406/mac
- QMK FAQ (TMK relationship): https://docs.qmk.fm/#/faq_general
- QMK Toolbox: https://github.com/qmk/qmk_toolbox
- usbipd-win: https://learn.microsoft.com/windows/wsl/connect-usb
