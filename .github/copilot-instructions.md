# Copilot Instructions

## Project Overview

Two firmwares for two keyboards that share one behaviour ("Dwerty"): the base layer types Dvorak, but holding or one-shotting Ctrl/Alt/Win sends the key in its Qwerty physical position, so shortcuts (Ctrl+C, Ctrl+V, etc.) stay in muscle memory. The OS stays on US Qwerty and Shift is excluded so shifted letters still type Dvorak.

| Directory | Keyboard | Firmware | SoC |
|-----------|----------|----------|-----|
| `max/` | Keychron V6 Max | QMK | shipping |
| `ultra/` | Keychron V6 Ultra 8K | ZMK | Realtek RTL8762G (spike) |

Each directory is self-contained, with its own build scripts, tests and README. They share no toolchain.

## `max/` — QMK (Keychron V6 Max)

The keymap (`max/keymaps/keychron/v6_max/ansi_encoder/keymaps/dvorak_qwerty/keymap.c`) defines 4 layers:

- **DWERTY (0)** — Dvorak typing with Qwerty shortcut interception
- **QWERTY (1)** — Plain Qwerty layout (no shortcut remapping)
- **DVORAK (2)** — Pure Dvorak typing (no shortcut remapping)
- **FN (3)** — Fn-held overlay (F-keys, RGB, Bluetooth, layout selector)

DWERTY and DVORAK share the same physical key layout. The difference: `qwerty_shortcuts_layer_active()` returns `true` only for DWERTY. All base layers use `MO(FN)` for the Fn key.

A `layout_mode_t` enum (DWERTY=0, QWERTY=1, DVORAK=2) is persisted in EEPROM user data. `apply_layout_mode(mode)` sets the default layer via `default_layer_set(1UL << mode)`. The upstream DIP switch handler in `v6_max.c` is overridden by `dip_switch_update_user()` to always apply the saved mode.

Shortcut interception works by maintaining a `qwerty_shortcut_map[]` lookup table that maps Dvorak keycodes to their Qwerty equivalents. When a modifier (Ctrl/Alt/GUI) is held on the DWERTY layer, `process_record_user` intercepts the keypress and sends the Qwerty equivalent instead. The `qwerty_shortcut_active[]` matrix tracks which remapped key is physically held so the correct keycode is unregistered on release — this release path must run before the modifier check.

**Build and test (run from `max/`):**
```bash
./scripts/firmware.sh build    # build only (Podman container, see Containerfile)
./scripts/firmware.sh flash    # flash only
./scripts/firmware.sh          # build + flash (default)
./scripts/test.sh              # Python unittest suite
```

The build clones Keychron's QMK fork (`wireless_playground` branch) into `max/.cache/qmk_keychron/` and copies the keymap in before compiling.

**`max/` conventions:**
- The keymap directory mirrors the QMK keyboard path. The build script copies it into the QMK tree at compile time.
- When adding or removing keys from `qwerty_shortcut_map[]` in `keymap.c`, update the `EXPECTED` set in `max/tests/test_shortcuts_mapping.py` to match.
- `config.h` sets `DYNAMIC_KEYMAP_LAYER_COUNT 4` — update this if adding layers.
- `via/v6_max_ansi_encoder.json` is the VIA draft definition for live remapping.
- Shift is intentionally excluded from shortcut mod masks so shifted keys produce Dvorak characters, not Qwerty.

## `ultra/` — ZMK (Keychron V6 Ultra 8K)

The V6 Ultra runs ZMK on a Realtek RTL8762G. The Dwerty behaviour is reproduced with per-key `&mod_morph` behaviours: each differing key binds its Dvorak letter normally and its Qwerty-position letter when Ctrl/Alt/GUI is held, with `keep-mods` keeping the modifier in the output. One-shot (`&sk`) modifiers trigger the morph identically to held modifiers.

**Build (Keychron fork) vs test (upstream ZMK) — two separate toolchains:**
- **Build** the real firmware on Keychron's fork (`Keychron/zmk@rtl8762g`), board `keychron`, shield `keychron_v6_ultra_ansi`, container `zmk-build-arm:3.5`.
- **Test** behaviour on upstream `zmkfirmware/zmk` `native_sim` snapshot tests (container `zmk-build-arm:4.1`). The Keychron fork cannot host-test because its core headers include the Realtek HAL header `rtl_pinmux.h`. `&mod_morph`+`keep-mods` is identical between fork and upstream, so behaviour proven on upstream holds for the real firmware.

```bash
cd ultra
./scripts/build.sh   # real firmware on the Keychron fork
./scripts/test.sh    # native_sim behaviour tests on upstream ZMK
```

**`ultra/` conventions:**
- The build board is `keychron`, **not** `rtl8762gtu_kb` (a plain build fails on the undefined `RTK_DFU` symbol).
- Keep the Dvorak→Qwerty pairs identical to `max`'s `qwerty_shortcut_map[]`. When that map changes, update both firmwares.
- Behaviour tests are ZMK `native_sim` snapshots (`tests/<case>/native_sim.keymap` + `events.patterns` + `keycode_events.snapshot`).
- Flashing uses Realtek DFU (no UF2). The RTK `prepend_header` packaging tool is x86_64-only and fails on aarch64 hosts.

## CI & releases

Two GitHub Actions workflows, one per keyboard:
- `.github/workflows/firmware-max.yml` (**Build Max Firmware**) builds the QMK firmware on push to `main`, on PRs touching `max/**`, and on `max-v*` tags.
- `.github/workflows/firmware-ultra.yml` (**Build Ultra Firmware**) runs only on `ultra-v*` tags and `workflow_dispatch` (the ZMK build is slow). It reuses `ultra/scripts/{test,build,package}.sh` with `DWERTY_CONTAINER_ENGINE=docker`.

Releases are per keyboard and share one **Dwerty** project version: tag `max-v<x.y.z>` or `ultra-v<x.y.z>`. That Dwerty version is our own; it is separate from the **Keychron anchor** each firmware reports for compatibility (V6 Max `DEVICE_VER` 1.1.2; V6 Ultra fork `app/VERSION` 1.0.2). The V6 Ultra release is published as an experimental pre-release (not yet hardware-verified) and includes the Realtek `zmk_ota_MP.bin`.
