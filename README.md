# Dvorak + Qwerty Shortcuts for Keychron V6 Max (Windows-first)

Firmware keymap for the Keychron V6 Max (ANSI knob) that types **Dvorak** while keeping **Qwerty-position shortcuts**. The OS stays US Qwerty. Windows behavior is the priority; macOS support is included where it is easy.

## Project requirements
- **Target**: Keychron V6 Max (ANSI knob unless otherwise specified).
- **Behavior**: firmware-level Dvorak with Qwerty-position shortcuts (“Dvorak‑QWERTY Command”), OS remains US Qwerty.
- **Platforms**: Windows first; macOS supported when low effort.
- **Hardware parity**: preserve all keys, encoder, media, and lighting effects.
- **UI editing**: post‑flash UI editing via VIA/Keychron Launcher (or UI‑only flow).
- **Testing**: unit tests and integration tests (no hardware required when possible).
- **Updates**: able to update to latest framework versions when required.
- **Safety**: documented rollback path.
- **Ops**: WSL-first dev/testing and flashing instructions; CI workflows for tests.
- **Approach**: maintain an audit of frameworks/tooling vs manufacturer guidance in this README.

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

## Flashing
### Preferred: Keychron Launcher (official)
- Use Keychron Launcher to flash the compiled `.bin` or official firmware.
- Launcher requires a wired USB connection.

### CLI (QMK CLI or make)
```bash
QMK_DIR=~/qmk_firmware ./scripts/flash.sh
```
This prompts you to enter bootloader mode (hold **Esc** while plugging in with cable).

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

## Tests
All tests (unit + integration simulation):
```bash
./scripts/test.sh
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
1. Install Podman and ensure it is configured for rootless use.
2. In VS Code, install the **Dev Containers** extension.
3. Open this repo and run: **Dev Containers: Reopen in Container**.
4. The container uses the same `Containerfile` as the Podman scripts.

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
