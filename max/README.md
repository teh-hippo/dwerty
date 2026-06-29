# Dwerty — Keychron V6 Max

[![Build Max Firmware](https://github.com/teh-hippo/dwerty/actions/workflows/firmware-max.yml/badge.svg)](https://github.com/teh-hippo/dwerty/actions/workflows/firmware-max.yml)

Custom QMK firmware for the Keychron V6 Max (ANSI knob). Types **Dvorak** while keeping **Qwerty-position shortcuts** (Ctrl+C, Ctrl+V, etc.). The OS stays on US Qwerty — all remapping happens in firmware.

Based on Keychron's QMK fork ([`wireless_playground`](https://github.com/Keychron/qmk_firmware/tree/wireless_playground) branch). Reports firmware version **1.1.2** to match the latest official V6 Max release. Pre-built binaries are available on the [Releases](../../releases) page.

## Layers

The Mac/Win slide switch chooses the OS half; the saved Dwerty/Qwerty choice picks which base shows in that half.

| Layer | Index | Description |
|-------|-------|-------------|
| MAC_QWERTY | 0 | Mac Qwerty base (stock) |
| MAC_DWERTY | 1 | Mac Dvorak keys + Qwerty shortcut interception |
| WIN_QWERTY | 2 | Win Qwerty base (stock) |
| WIN_DWERTY | 3 | Win Dvorak keys + Qwerty shortcut interception |
| FN | 4 | Fn-held overlay |

The Dwerty layers type Dvorak; when you hold Ctrl/Alt/Win, the firmware intercepts and sends the Qwerty-position shortcut. The Qwerty layers are the stock Keychron bases with no remapping.

The Dwerty/Qwerty choice is persisted in EEPROM and survives reboots and Mac/Win switches.

## Layout Selector

Hold **Fn**, press **Z** to toggle between Dwerty and Qwerty within the current OS half. A circular animation on the Z, A, S, X keys shows the current mode. Release Fn to confirm.

| Mode | Tab LED | Selector colour |
|------|---------|-----------------|
| Dwerty | 🔴 Red | Red |
| Qwerty | 🔵 Blue | Blue |

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

Requires [Podman](https://podman.io). Builds inside a container (`debian:trixie-slim`) using Keychron's QMK fork. Run these from the `max/` directory (or prefix with `max/`):

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
| **Keychron firmware version** (1.1.2) | USB `DEVICE_VER`, pinned to the official Keychron V6 Max release so the Launcher and VIA treat it as compatible firmware. | `config.h` (`DEVICE_VER`) |
| **Dwerty version** (e.g. 1.0.0) | Our own project version, shared across both the V6 Max and V6 Ultra firmwares. It tracks our layout and build changes and need not match the Keychron firmware version. | Git tags, GitHub Releases |

Releases are per keyboard. The V6 Max is tagged **`max-v<dwerty>`** (the V6 Ultra is `ultra-v<dwerty>`), so one shared Dwerty version covers both keyboards while each is released independently. Each tag builds that keyboard and publishes a GitHub Release with the `.bin`, `.hex` and SHA256 sums attached.

### Downloading firmware

Pre-built `.bin` and `.hex` files are attached to [GitHub Releases](../../releases). Each release includes SHA256 checksums for verification. See [Flashing a release](#flashing-a-release) below.

> **Note:** QMK embeds the build date in the binary. VIA uses this to detect firmware changes and may reset your keymaps when flashing a binary built on a different date than your current firmware. This is standard QMK/VIA behaviour, not specific to this project.

### Flashing a release

Two easy ways to flash a published release, with no local build.

**WSL (one command).** From `max/`, with the [GitHub CLI](https://cli.github.com) signed in:

```bash
./scripts/firmware.sh flash-release             # newest max-v* release
./scripts/firmware.sh flash-release max-v2.1.0  # a specific tag
```

It downloads the release `.bin` with `gh`, verifies the SHA256, then DFU-flashes it. Put the keyboard in bootloader first (hold **Esc** while plugging in USB); on WSL the script attaches the device with `usbipd` automatically.

**Windows (no WSL).** Download the `.bin` from the [Releases](../../releases) page (or `gh release download <tag>`), open [QMK Toolbox](https://github.com/qmk/qmk_toolbox), put the keyboard in bootloader (hold **Esc** while plugging in USB), and flash the `.bin`. QMK Toolbox auto-detects the STM32 DFU device.

The Keychron Launcher only flashes Keychron-hosted firmware, so it cannot flash these custom builds.

### Creating a release

```bash
git tag max-v1.0.0
git push origin max-v1.0.0
```

The `Build Max Firmware` workflow builds the firmware and publishes the release with the `.bin`, `.hex` and `.sha256` attached.

## Tests

```bash
./scripts/test.sh
```

## VIA / Keychron Launcher

The firmware supports both [usevia.app](https://usevia.app) and the [Keychron Launcher](https://launcher.keychron.com).

**usevia.app** — Load `via/v6_max_ansi_encoder.json` as a draft definition (Design tab). Custom keycodes (LAYOUT_TG, LAYOUT_SEL, etc.) are available for remapping.

**Keychron Launcher** — Connects automatically. Advanced menu (snap click, per-key RGB, bounce time) is enabled. Custom keycodes are not visible in the Launcher (they use a hardcoded JSON).

## Keychron Compatibility

| Feature | Status |
|---------|--------|
| VIA JSON (VID/PID/matrix/layouts/menus) | ✅ Exact match with upstream |
| Wireless (Bluetooth, 2.4G) | ✅ Enabled at board level |
| Snap click | ✅ Enabled (build-time patch) |
| Per-key RGB / Mixed RGB | ✅ Enabled (build-time patch) |
| Firmware version | ✅ Reports 1.1.2 (DEVICE_VER override in config.h) |
| Debounce | ✅ Adjustable in the Launcher ("bounce time"); defaults to `sym_eager_pk` @ 50ms |
| DIP switch (Mac/Win toggle) | ✅ Honoured — selects the Mac or Win base; saved Dwerty/Qwerty choice applies within the half |
