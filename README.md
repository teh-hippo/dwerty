# Dvorak + Qwerty Shortcuts for Keychron V6 Max (Windows-first)

_Last updated: January 2025_

Firmware keymap for the Keychron V6 Max (ANSI knob) that types **Dvorak** while keeping **Qwerty-position shortcuts**. The OS stays US Qwerty. Windows behavior is the priority; macOS support is included where it is easy.

## Quick Start

1. **Setup QMK**: `./scripts/setup_qmk.sh`
2. **Build firmware**: `QMK_DIR=~/qmk_firmware ./scripts/build.sh --artifacts`
3. **Flash to keyboard**: `QMK_DIR=~/qmk_firmware ./scripts/flash.sh --easy`
4. **Run tests**: `./scripts/test.sh`
5. **Run linting**: `./scripts/lint.sh`

See detailed instructions below for WSL workflows, Podman builds, and VS Code integration.

## Requirements Checklist

This project addresses all original requirements:

| Requirement | Implementation |
|-------------|----------------|
| **Custom keyboard layout** | Firmware-level Dvorak with Qwerty-position shortcuts for Keychron V6 Max (ANSI knob) |
| **"Dvorak-QWERTY Command"** | Windows: Ctrl/Alt/GUI trigger Qwerty positions; macOS: Command triggers Qwerty positions |
| **Windows primary platform** | Windows-first shortcut behavior; macOS support included when low effort |
| **Hardware features retained** | All keys, lighting, media, and encoder (knob) behavior preserved from stock keymap |
| **UI editing support** | VIA-enabled for post-flash editing; Keychron Launcher compatible |
| **Thorough testing** | Unit tests ([`tests/test_shortcuts_mapping.py`](tests/test_shortcuts_mapping.py)), integration tests ([`tests/test_integration_simulation.py`](tests/test_integration_simulation.py)), UAT guidance ([`docs/INTEGRATION_TESTING.md`](docs/INTEGRATION_TESTING.md)) |
| **WSL-first instructions** | WSL workflow documented for build/flash (see [WSL-first workflow](#wsl-first-workflow-recommended-for-windows-users) section) |
| **Easy updates** | [`./scripts/update_qmk.sh`](scripts/update_qmk.sh) to update QMK firmware base |
| **Linting and code standards** | Python (ruff), Shell (shellcheck), C (clang-format) via [`./scripts/lint.sh`](scripts/lint.sh) |
| **VS Code integration** | Tasks, debugging, IntelliSense configured (see [VS Code Integration](#vs-code-integration) section) |
| **Streamlined building** | Podman-based containerized builds via [`./scripts/build.sh --podman`](scripts/build.sh) |
| **Rollback instructions** | Documented in [Backup / rollback](#backup--rollback) section |

## Behavior (Windows-first)
- **Windows base layers**: when **Ctrl/Alt/GUI** is held, send Qwerty-position keycodes for shortcuts.
- **macOS base layers**: when **Command (GUI)** is held, send Qwerty-position keycodes (mirrors macOS "Dvorak - QWERTY Command").
- Shift alone does **not** trigger remaps.
- Remap applies only on base layers.
- Remapped keys are always unregistered on release, even if modifiers were released first.
- Encoder and media behavior match the stock keymap.

Tooling decision and audit summary is recorded below.

## Tooling decision (as of January 14, 2026)
- **Manufacturer guidance**: Keychron’s official workflow for firmware flashing uses the Keychron Launcher in Cable mode and requires a bootloader entry (hold Esc while plugging in). This is the supported path for recovery and rollback.
- **Official firmware cadence**: The V6 Max firmware page lists versions up to **1.1.2** (May 15, 2025) with fixes for debounce, lighting effects, and knob behavior. This is the last official release date we should assume as a baseline.
- **QMK upstream vs Keychron fork**:
  - Upstream QMK still lacks `keychron/v6_max` support (the upstream `info.json` path 404s).
  - Keychron’s fork contains V6 Max definitions (the `info.json` is present on `wireless_playground`).
  - Keychron’s `qmk_firmware` fork shows recent activity (updated Dec 22, 2025 on the Keychron GitHub org listing), so it is not abandoned, but it may still lag upstream QMK.
- **VIA support**: VIA requires firmware-side enablement (`VIA_ENABLE = yes`) and a compatible keymap target. This repo enables VIA in the keymap so post-flash UI editing is available.
- **TMK context**: QMK is a fork of TMK and builds on it with a larger feature set and broader keyboard support; TMK alone would require a custom port for V6 Max.

Decision: use the Keychron QMK fork (`wireless_playground`) until upstream adds V6 Max; keep Launcher and VIA compatibility for UI edits and rollback.

## UI-based editing after flash
This keymap is **VIA-enabled** and **Launcher-compatible**:
- **Keychron Launcher (official)**: recommended for remaps and firmware flashing. Requires a wired USB connection and a Chromium-based browser.
- **VIA**: supported for post-flash edits. If VIA does not recognize the board, load the V6 Max JSON from Keychron's firmware/JSON page.

## Build prerequisites
- QMK toolchain installed (QMK CLI or `make`).
- QMK tree with `keychron/v6_max` support (Keychron fork by default).

### WSL/Ubuntu dependency install (one-time)
```bash
python3 -m pip install --user qmk
sudo apt-get update
sudo apt-get install -y gcc-arm-none-eabi gcc-avr avr-libc avrdude dfu-programmer dfu-util dos2unix libnewlib-arm-none-eabi
```

## Setup
1. Clone a QMK tree that supports V6 Max:
   ```bash
   ./scripts/setup_qmk.sh
   ```

2. Copy the keymap into the QMK tree:
   ```bash
   QMK_DIR=~/qmk_firmware ./scripts/install_keymap.sh
   ```

3. Build the firmware:
   ```bash
   QMK_DIR=~/qmk_firmware ./scripts/build.sh
   ```

4. Optional: copy build artifacts into `./build/`:
   ```bash
   QMK_DIR=~/qmk_firmware ./scripts/build.sh --artifacts
   ```

## Flashing
### Keychron Launcher (official firmware path)
- Use Keychron Launcher to flash **official firmware**.
- Launcher requires a wired USB connection.
- Use the latest Chrome, Edge, or Opera for the Launcher web app.
- The official flow does not describe selecting a local `.bin` file.

### Custom firmware (this repo) via QMK Toolbox (Windows/macOS)
1. Build and copy artifacts:
   ```bash
   QMK_DIR=~/qmk_keychron ./scripts/build.sh --artifacts
   ```
2. Open QMK Toolbox and load `build/keychron_v6_max_ansi_encoder_dvorak_qwerty.bin`.
3. Put the keyboard in bootloader mode (hold **Esc** while plugging in USB).
4. Click **Flash**.

### Custom firmware (this repo) via CLI (QMK CLI or make)
#### Standard flash
```bash
QMK_DIR=~/qmk_firmware ./scripts/flash.sh
```
This prompts you to enter bootloader mode (hold **Esc** while plugging in with cable).

#### Easy flash (install keymap + build + flash in one step)
```bash
QMK_DIR=~/qmk_firmware ./scripts/flash.sh --easy
```

## Backup / rollback
- Download the official V6 Max firmware from Keychron's firmware page.
- Flash it with Keychron Launcher (preferred) or QMK Toolbox.

## Updating QMK (firmware base)
Use this when you want a newer QMK version while keeping the keymap overlay clean:
```bash
QMK_DIR=~/qmk_firmware ./scripts/update_qmk.sh
```
Notes:
- The script refuses to update if your QMK repo has local changes.
- It keeps the current branch unless `QMK_BRANCH` is set.
- It verifies `keychron/v6_max` still exists after the update.

## WSL-first workflow (recommended for Windows users)
### Option A: build in WSL, flash in Windows
1. Build in WSL:
   ```bash
   QMK_DIR=~/qmk_firmware ./scripts/build.sh
   ```
2. Copy the `.bin` to Windows and flash using Keychron Launcher or QMK Toolbox.

### Option B: USB passthrough with usbipd-win
1. Install **usbipd-win** on Windows and ensure you are using WSL 2.
2. List devices (Windows PowerShell):
   ```powershell
   usbipd list
   ```
3. Attach the device to WSL (Admin PowerShell):
   ```powershell
   .\scripts\wsl_attach_usb.ps1 -BusId <BUSID>
   ```
4. Confirm visibility in WSL:
   ```bash
   lsusb
   ```
5. Flash from WSL:
   ```bash
   QMK_DIR=~/qmk_firmware ./scripts/flash.sh
   ```
6. Detach when done:
   ```powershell
   usbipd detach --busid <BUSID>
   ```

### WSL + usbipd UAT workflow (manual smoke test)
See `docs/INTEGRATION_TESTING.md` for the full checklist.

## Linting
The project includes linting configuration for code quality:

### Run all linters
```bash
./scripts/lint.sh
```

### Run specific linters
```bash
./scripts/lint.sh --python   # Python files (ruff)
./scripts/lint.sh --shell    # Shell scripts (shellcheck)
./scripts/lint.sh --c        # C code formatting (clang-format)
```

### Linting tools
- **Python**: `ruff` (configured in [`pyproject.toml`](pyproject.toml))
- **Shell scripts**: `shellcheck` (configured in [`.shellcheckrc`](.shellcheckrc))
- **C code**: `clang-format` (configured in [`.clang-format`](.clang-format), aligned with QMK style)

### Install linting tools
```bash
pip install ruff
sudo apt-get install shellcheck clang-format
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
./scripts/test_integration.sh
```
These tests simulate modifier + layer behavior in a dummy firmware model. They do not emulate USB/Bluetooth timing, wireless stacks, or true hardware scans.

Integration test plan and expansion notes:
- See `docs/INTEGRATION_TESTING.md`.

Optional QMK build check (network + toolchain required):
```bash
./scripts/test_qmk_build.sh
```

## Podman workflows (preferred container path)
### Build the container image
```bash
./scripts/podman_build.sh
```

### Run a container shell
```bash
./scripts/podman_run.sh
```

From inside the container you can run:
```bash
./scripts/test_qmk_build.sh
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
