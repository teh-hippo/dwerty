# Dwerty — Keychron V6 Max

QMK firmware keymap for the Keychron V6 Max (ANSI knob). Types **Dvorak** while keeping **Qwerty-position shortcuts** (Ctrl+C, Ctrl+V, etc.). The OS stays on US Qwerty — all remapping happens in firmware.

## Layout Modes

Three selectable modes, cycled with **Fn + Z**:

| Mode | Tab LED | Description |
|------|---------|-------------|
| **Dwerty** | 🔴 Red | Dvorak typing + Qwerty shortcuts (Ctrl+C sends Ctrl+C) |
| **Qwerty** | 🔵 Blue | Standard Qwerty layout |
| **Dvorak** | 🟢 Green | Pure Dvorak (Ctrl+C sends Ctrl+J — no shortcut remapping) |

Hold **Fn**, press **Z** to enter the layout selector. A circular animation on the Z, A, S, X keys shows the current mode. Each press of Z cycles to the next mode. Release Fn to confirm. The selection persists across reboots.

## Fn Layer (Qwerty key positions)

| Key | Function | | Key | Function |
|-----|----------|-|-----|----------|
| Z | Layout selector | | 1/2/3 | Bluetooth hosts |
| Tab | RGB toggle | | 4 | 2.4G |
| Q/A | RGB effect ↑/↓ | | B | Battery level |
| W/S | RGB brightness ↑/↓ | | N | N-key rollover toggle |
| E/D | RGB hue ↑/↓ | | Encoder | RGB brightness ↑/↓ |
| R/F | RGB saturation ↑/↓ | | | |
| T/G | RGB speed ↑/↓ | | | |

## Build & Flash

Requires Podman. The build runs in a container using Keychron's QMK fork (`wireless_playground` branch).

```bash
./scripts/firmware.sh build    # build only
./scripts/firmware.sh flash    # flash only (hold Esc while plugging in USB first)
./scripts/firmware.sh          # build + flash
```

On WSL, attach the USB bootloader device first:

```powershell
usbipd list
usbipd bind --busid <BUSID>
usbipd attach --wsl --busid <BUSID>
```

## Tests

```bash
./scripts/test.sh
```

## VIA

1. Open [usevia.app](https://usevia.app)
2. Settings → Enable "Show Design tab"
3. Design tab → Load `via/v6_max_ansi_encoder.json`
4. Configure tab → Authorize device
