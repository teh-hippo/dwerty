# Approach Comparison (Updated January 13, 2026)

## Goal
Use the cleanest, most up-to-date QMK codebase possible while still supporting the Keychron V6 Max (ANSI knob).

## Option A — Upstream QMK (`qmk/qmk_firmware`)
**Pros**
- Clean, canonical upstream QMK tree.
- Most current QMK features and community fixes.

**Cons**
- As of **January 13, 2026**, `keyboards/keychron/v6_max` is **not present** upstream.
- Without upstream support, you would need to port the V6 Max keyboard definition (wireless, MCU, matrix, encoder) into upstream QMK.

**When to use**
- Only if upstream adds official V6 Max support or you’re prepared to maintain a port.

## Option B — Keychron QMK fork (`Keychron/qmk_firmware`, `wireless_playground`)
**Pros**
- Officially includes `keyboards/keychron/v6_max` and wireless support.
- Matches Keychron’s firmware tooling and layouts for the V6 Max.

**Cons**
- Not upstream; may lag QMK mainline or include vendor‑specific changes.

**When to use**
- **Recommended today** for V6 Max because it is the only known official source tree with V6 Max support.

## Decision
We will use **Option B** (Keychron fork) by default, but keep this repo as a **clean overlay** so you can switch to upstream if/when V6 Max is merged there.

## Verification used
- `https://raw.githubusercontent.com/qmk/qmk_firmware/master/keyboards/keychron/v6_max/info.json` → 404 (missing)
- `https://raw.githubusercontent.com/Keychron/qmk_firmware/wireless_playground/keyboards/keychron/v6_max/info.json` → 200 (present)
