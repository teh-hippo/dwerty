# Dvorak + Qwerty Shortcuts for Keychron V6 Max

Firmware keymap for the Keychron V6 Max (ANSI knob) that types **Dvorak** while keeping **Qwerty-position shortcuts**. The OS stays US Qwerty.

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
- **Fn + Z/X**: Cycle layers
- **VIA: `LAYOUT_DVORAK`/`LAYOUT_QWERTY`**: Set default layer

**Fn Layer**
- Lighting controls: Tab (toggle), Q/A (effects), W/S (brightness), E/D (hue), R/F (saturation), T/G (speed)
- Encoder: Brightness up/down
- Connectivity: 1/2/3 (Bluetooth), 4 (2.4G), B (battery), N (N-key rollover)

## VIA Support

**First time setup:**
1. Open [usevia.app](https://usevia.app)
2. Settings → Enable "Show Design tab"
3. Design tab → "Load Draft Definition" → Select `via/v6_max_ansi_encoder.json`
4. Configure tab → Authorize device

After loading once, VIA remembers your keyboard. You can then remap keys in real-time without reflashing.
