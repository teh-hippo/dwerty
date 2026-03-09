# Copilot Instructions

## Project Overview

QMK firmware keymap for the Keychron V6 Max (ANSI knob) that types Dvorak while keeping Qwerty-position shortcuts (Ctrl+C, Ctrl+V, etc.). The OS stays on US Qwerty — all remapping happens in firmware via `process_record_user`.

## Architecture

The keymap (`keymaps/keychron/v6_max/ansi_encoder/keymaps/dvorak_qwerty/keymap.c`) defines 4 layers:

- **DWERTY (0)** — Dvorak typing with Qwerty shortcut interception
- **QWERTY (1)** — Plain Qwerty layout (no shortcut remapping)
- **DVORAK (2)** — Pure Dvorak typing (no shortcut remapping)
- **FN (3)** — Fn-held overlay (F-keys, RGB, Bluetooth, layout selector)

DWERTY and DVORAK share the same physical key layout. The difference: `qwerty_shortcuts_layer_active()` returns `true` only for DWERTY. All base layers use `MO(FN)` for the Fn key.

A `layout_mode_t` enum (DWERTY=0, QWERTY=1, DVORAK=2) is persisted in EEPROM user data. `apply_layout_mode(mode)` sets the default layer via `default_layer_set(1UL << mode)`. The upstream DIP switch handler in `v6_max.c` is overridden by `dip_switch_update_user()` to always apply the saved mode.

Shortcut interception works by maintaining a `qwerty_shortcut_map[]` lookup table that maps Dvorak keycodes to their Qwerty equivalents. When a modifier (Ctrl/Alt/GUI) is held on the DWERTY layer, `process_record_user` intercepts the keypress and sends the Qwerty equivalent instead. The `qwerty_shortcut_active[]` matrix tracks which remapped key is physically held so the correct keycode is unregistered on release — this release path must run before the modifier check.

## Build & Test

**Build firmware** (requires Podman and USB for flashing):
```bash
./scripts/firmware.sh build    # build only
./scripts/firmware.sh flash    # flash only
./scripts/firmware.sh          # build + flash (default)
```

The build runs inside a Podman container (see `Containerfile`). It clones Keychron's QMK fork (`wireless_playground` branch) into `.cache/qmk_keychron/` and copies the keymap in before compiling.

**Run tests:**
```bash
./scripts/test.sh                                              # all tests
python -m unittest tests.test_shortcuts_mapping                # all tests in module
python -m unittest tests.test_shortcuts_mapping.ShortcutMappingTests.test_mapping_table_matches_expected  # single test
```

Tests are Python `unittest` and validate:
1. The `qwerty_shortcut_map[]` entries match the expected Dvorak→Qwerty pairs
2. Shortcut mod mask excludes Shift (so Shift+key still types Dvorak)
3. The release path in `process_record_user` runs before modifier checks
4. Layout mode enum exists with all three modes
5. Shortcut interception only activates on the DWERTY layer

## Key Conventions

- The keymap directory mirrors the QMK keyboard path: `keymaps/keychron/v6_max/ansi_encoder/keymaps/dvorak_qwerty/`. The build script copies this into the QMK tree at compile time.
- When adding or removing keys from `qwerty_shortcut_map[]` in `keymap.c`, update the `EXPECTED` set in `tests/test_shortcuts_mapping.py` to match.
- `config.h` sets `DYNAMIC_KEYMAP_LAYER_COUNT 4` — update this if adding layers.
- `via/v6_max_ansi_encoder.json` is the VIA draft definition for live remapping.
- Shift is intentionally excluded from shortcut mod masks so shifted keys produce Dvorak characters, not Qwerty.
