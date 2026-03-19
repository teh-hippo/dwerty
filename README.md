# Dwerty — Keychron V6 Max

[![Build Firmware](https://github.com/teh-hippo/dwerty/actions/workflows/firmware.yml/badge.svg)](https://github.com/teh-hippo/dwerty/actions/workflows/firmware.yml)

Custom QMK firmware for the Keychron V6 Max (ANSI knob). Types **Dvorak** while keeping **Qwerty-position shortcuts** (Ctrl+C, Ctrl+V, etc.). The OS stays on US Qwerty — all remapping happens in firmware.

Based on Keychron's QMK fork ([`wireless_playground`](https://github.com/Keychron/qmk_firmware/tree/wireless_playground) branch). Reports firmware version **1.1.2** to match the latest official V6 Max release. Pre-built binaries are available on the [Releases](../../releases) page.

## Layers

| Layer | Index | Description |
|-------|-------|-------------|
| DWERTY | 0 | Dvorak keys + Qwerty shortcut interception |
| QWERTY | 1 | Standard Qwerty |
| DVORAK | 2 | Pure Dvorak (no shortcut interception) |
| FN | 3 | Fn-held overlay |

DWERTY and DVORAK have identical key layouts. The only difference: when you hold Ctrl/Alt/Win on DWERTY, the firmware intercepts and sends the Qwerty-equivalent shortcut. On DVORAK, no interception occurs.

The selected mode is persisted in EEPROM and survives reboots.

## Layout Selector

Hold **Fn**, press **Z** to enter the layout selector. A circular animation on the Z, A, S, X keys shows the current mode. Each press of Z cycles to the next mode. Release Fn to confirm.

| Mode | Tab LED | Selector colour |
|------|---------|-----------------|
| Dwerty | 🔴 Red | Red |
| Qwerty | 🔵 Blue | Blue |
| Dvorak | 🟢 Green | Green |

## Fn Layer

Key positions are labelled by their Qwerty location on the physical keyboard.

| Key | Function | | Key | Function |
|-----|----------|-|-----|----------|
| Z | Layout selector | | 1/2/3 | Bluetooth hosts |
| / | Help overlay | | 4 | 2.4G |
| Tab | RGB toggle | | B | Battery level (wireless only) |
| Q/A | RGB effect ↑/↓ | | N | N-key rollover |
| W/S | RGB brightness ↑/↓ | | Knob | RGB brightness |
| E/D | RGB hue ↑/↓ | | | |
| R/F | RGB saturation ↑/↓ | | | |
| T/G | RGB speed ↑/↓ | | | |

## Help Overlay

Press **Fn+/** to light up all Fn feature keys with self-describing animations. Each key demonstrates its function through its LED behaviour (e.g., brightness keys pulse bright/dim, hue keys cycle colours, speed keys flash fast/slow). Press any key or release Fn to exit.

## Build & Flash

Requires [Podman](https://podman.io). Builds inside a container (`debian:trixie-slim`) using Keychron's QMK fork.

```bash
./scripts/firmware.sh build    # build only
./scripts/firmware.sh flash    # flash only
./scripts/firmware.sh          # build + flash
```

The build script patches the upstream V6 Max keyboard config at compile time to enable snap click, per-key RGB, and the eeconfig include order fix — matching the changes Keychron applied to V3 Max but not yet to V6 Max on the `wireless_playground` branch.

To enter bootloader: hold **Esc** while plugging in USB.

### WSL

Attach the USB bootloader device before flashing:

```powershell
# One-time (Admin PowerShell):
usbipd bind --busid <BUSID>

# Each flash:
usbipd attach --wsl --busid <BUSID>
```

The flash script auto-detects and attaches if `usbipd.exe` is in PATH.

## Releases & Versioning

This project uses two independent version numbers:

| Version | What it means | Where it lives |
|---------|---------------|----------------|
| **Keychron firmware version** (e.g. 1.1.2) | USB `DEVICE_VER` — pinned to the official Keychron release we're based on. The Launcher uses this to identify firmware compatibility. | `config.h` (`DEVICE_VER`) |
| **Dwerty release** (e.g. dwerty-1.0.0) | Our keymap/project version. Tracks layout changes, build fixes, new features. | Git tags, GitHub Releases |

### Downloading firmware

Pre-built `.bin` files are attached to [GitHub Releases](../../releases). Each release includes a SHA256 checksum for verification. Flash with the [Keychron Launcher](https://launcher.keychron.com) or DFU tool.

> **Note:** QMK embeds the build date in the binary. VIA uses this to detect firmware changes and may reset your keymaps when flashing a binary built on a different date than your current firmware. This is standard QMK/VIA behaviour, not specific to this project.

### Creating a release

```bash
git tag dwerty-1.0.0
git push --tags
```

The GitHub Actions workflow builds the firmware and creates a release with the `.bin` and `.sha256` attached.

## Tests

```bash
./scripts/test.sh
```

## VIA / Keychron Launcher

The firmware supports both [usevia.app](https://usevia.app) and the [Keychron Launcher](https://launcher.keychron.com).

**usevia.app** — Load `via/v6_max_ansi_encoder.json` as a draft definition (Design tab). Custom keycodes (LAYOUT_TG, LAYOUT_SEL, etc.) are available for remapping.

**Keychron Launcher** — Connects automatically. Advanced menu (snap click, per-key RGB) is enabled. Custom keycodes are not visible in the Launcher (they use a hardcoded JSON).

## Keychron Compatibility

| Feature | Status |
|---------|--------|
| VIA JSON (VID/PID/matrix/layouts/menus) | ✅ Exact match with upstream |
| Wireless (Bluetooth, 2.4G) | ✅ Enabled at board level |
| Snap click | ✅ Enabled (build-time patch) |
| Per-key RGB / Mixed RGB | ✅ Enabled (build-time patch) |
| Firmware version | ✅ Reports 1.1.2 (DEVICE_VER override in config.h) |
| Debounce | ✅ 50ms (matches official 1.1.2; upstream default is 20) |
| DIP switch (Mac/Win toggle) | ⚠️ Physical switch is ignored — firmware always applies saved layout mode |
