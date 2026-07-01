# Dwerty Ultra — Keychron V6 Ultra 8K (ZMK)

[![Build Ultra Firmware](https://github.com/teh-hippo/dwerty/actions/workflows/firmware-ultra.yml/badge.svg)](https://github.com/teh-hippo/dwerty/actions/workflows/firmware-ultra.yml)

ZMK firmware for the Keychron V6 Ultra 8K that reproduces the "Dwerty" behaviour from the QMK [`max/`](../max) firmware: the base layer types Dvorak, but holding or one-shotting Ctrl/Alt/Win sends the key in its Qwerty physical position (modifier kept), so shortcuts stay in muscle memory. Shift is excluded, so shifted letters still type Dvorak.

> Status: spike. The behaviour is proven with hardware-free tests and the firmware compiles for the real board. Flashing has not been exercised on hardware (see "Flashing").

## How it works

The V6 Ultra runs ZMK on a Realtek RTL8762G. Instead of QMK's runtime `process_record_user` interception, each differing key is a ZMK [`&mod_morph`](https://zmk.dev/docs/keymaps/behaviors/mod-morph): it binds its Dvorak letter normally and its Qwerty-position letter when Ctrl/Alt/GUI is held, with `keep-mods` keeping the modifier in the output. A one-shot (`&sk`) modifier registers an explicit modifier, so it triggers the morph exactly like a held modifier.

### Layers

| Layer | Name | Description |
|-------|------|-------------|
| 0 | MAC_QWERTY | Stock Mac base (Qwerty) |
| 1 | MAC_DWERTY | Mac Dvorak + 33 `&dq_*` Qwerty-position morphs |
| 2 | WIN_QWERTY | Stock Win base (Qwerty) |
| 3 | WIN_DWERTY | Win Dvorak + 33 `&dq_*` Qwerty-position morphs |
| 4 | FN | Stock RGB/Bluetooth/media overlay, shared by both halves |

This mirrors the QMK [`max/`](../max) firmware (which dropped pure Dvorak): the OS half (Mac/Win) and the Dvorak/Qwerty choice are the two base-layer pairs. The physical Mac/Win slide is a maintained GPIO. Rather than the stock momentary `&mo` overlay (which a marginal boot scan can miss, leaving the board stuck on Mac), our [`keymap.c` patch](patches/0001-persist-default-layer.patch) reads the slide GPIO level and sets the OS-half bit of the default layer at boot and on every edge, so the switch is honoured deterministically. The slide cell is therefore `&none`. Selecting the Win base swaps the F-row, the two Mac/Win special keys and the bottom-row modifier order to Windows while the Dwerty morphs keep working. The fn key is `&mo 4` on every base.

**Fn+Z** toggles Dwerty<->Qwerty within the current OS half (`0<->1`, `2<->3`) and **persists across reboot**. It is bound to `&to 0xFF`; our [`patches/0001-persist-default-layer.patch`](patches/0001-persist-default-layer.patch) treats `0xFF` as "flip the Dvorak/Qwerty bit of the default layer" and saves that one bit to settings, reloading it on boot. Only the Dvorak/Qwerty bit is persisted; the Mac/Win half always comes from the physical slide, so the switch always wins at boot. This is the ZMK mirror of QMK's `set_single_persistent_default_layer`.

Fn+Z also **flashes the whole board** for feedback (green = Dvorak, blue = Qwerty). The colour is painted at the PWM flush ([`patches/0002-rgb-dwerty-flash.patch`](patches/0002-rgb-dwerty-flash.patch)) so it overrides any effect, and it briefly forces the Keychron indicator render on (like the battery indicator) so it shows even when RGB is otherwise off.

The keymap is generated from the stock shield keymap by [`scripts/gen_keymap.py`](scripts/gen_keymap.py), which keeps Keychron's preamble (their custom behaviours, macros and combos) and rewrites only the layers and the toggle combo. Regenerate with:

```bash
python3 scripts/gen_keymap.py
```

## Build and test (two separate toolchains)

The build and the tests run against different ZMK trees, on purpose:

- **Build** the real firmware on Keychron's fork (`Keychron/zmk@rtl8762g`, pinned to commit `101a23c`), board `keychron`, shield `keychron_v6_ultra_ansi`, in the `zmk-build-arm:3.5` container. The build applies the patches in [`patches/`](patches) onto the fork's `app/src/` (idempotently): `0001` persists the layout choice and drives the Mac/Win slide from its GPIO, and `0002` adds the Fn+Z RGB flash.
- **Test** the behaviour on upstream `zmkfirmware/zmk` `native_sim` snapshot tests, in the `zmk-build-arm:4.1` container. The fork cannot host-test because its core headers pull in the Realtek HAL (`rtl_pinmux.h`). `&mod_morph` + `keep-mods` is identical between the fork and upstream, so behaviour proven on upstream holds for the real firmware.

Both need [Podman](https://podman.io), or Docker if you set `DWERTY_CONTAINER_ENGINE=docker` (CI uses Docker). Each toolchain is set up once into `.cache/` (gitignored); the first run downloads Zephyr and is slow.

```bash
./scripts/build.sh          # compile the real firmware -> ultra/build/zmk.{elf,hex,bin}
./scripts/build.sh --clean  # discard the cached fork workspace and start fresh

./scripts/test.sh                       # run all behaviour tests
./scripts/test.sh dvorak-qwerty         # run one test directory
```

### Tests

`tests/dvorak-qwerty/` holds ZMK `native_sim` snapshot tests that assert the exact HID output, plus a host-side parity check:

- `parity_dq.py` — asserts the 33 Dvorak->Qwerty pairs match `max/` exactly, so the two firmwares never drift.
- `1-dvorak-and-ctrl-qwerty` — tap types Dvorak; Ctrl+tap sends Ctrl+Qwerty; Shift+tap stays Dvorak.
- `2-oneshot-ctrl-qwerty` — a sticky (`&sk`) Ctrl still morphs the next key to its Qwerty position.
- `3-win-overlay-preserves-morph` — with the Mac/Win slide held to the Win Dwerty base, Ctrl+tap still sends Ctrl+Qwerty while the modifier position swaps Mac→Windows.
- `4-layout-toggle-switches-base` — the layout selector (`&to`) flips the base so the same key types Dvorak then Qwerty, proving the layer ordering. (The fork-only `&to 0xFF` half-toggle/persistence rides on the build, not native_sim.)

The persistent Fn+Z toggle lives in the `keymap.c` patch (settings on the fork), which `native_sim` cannot exercise; it is covered by the firmware build instead.

## The device

| Item | Value |
|------|-------|
| SoC | Realtek RTL8762G |
| Build board | `keychron` (not `rtl8762gtu_kb`; that fails on the undefined `RTK_DFU`) |
| Shield | `keychron_v6_ultra_ansi` |
| USB | VID `0x3434`, PID `0x0c60`, name "Keychron V6 Ultra 8K" |
| Config tool | Keychron Launcher (WebHID); no ZMK Studio in the fork |

## Flashing

Not yet exercised on hardware, but de-risked. From reading the fork's DFU code (`app/src/dfu/dfu_common.c`), the bootloader verifies image integrity with a SHA256 stored in the image header (no asymmetric code-signing) and any optional AES layer uses a key hardcoded in the open-source firmware. There is also a back-of-board button (P2_5) that enters an independent DFU app for recovery. So self-built images should be accepted via Keychron's Realtek CFU/DFU path.

The one snag is tooling, not signing: the Realtek `prepend_header` OTA packaging tool is x86_64-only. `build.sh` therefore treats the compiled `zmk.elf/hex/bin` as the deliverable and tolerates that last step failing. `scripts/package.sh` then produces the flashable image, running the x86 tool under `qemu-x86_64` on aarch64 hosts (needs `sudo apt-get install qemu-user`):

```bash
./scripts/package.sh   # -> ultra/build/zmk_ota_MP.bin (MP/CFU image)
```

This has been run successfully on aarch64, producing `zmk_ota.bin` (image header) and `zmk_ota_MP.bin` (MP/CFU image). The remaining step needs hardware: hold the back-of-board button to enter DFU and push `zmk_ota_MP.bin` with Keychron's `cfudownloadtool` (Windows). This voids warranty.

## Releases

Releases are published per keyboard from a Git tag. The V6 Ultra uses **`ultra-v<dwerty>`** tags, where `<dwerty>` is our shared Dwerty project version (the same scheme as the V6 Max's `max-v*`). That version is our own and need not match the Keychron firmware version the board reports (currently v1.0.2, the fork's ZMK app version).

Each `ultra-v*` tag runs the behaviour tests, builds the firmware on the Keychron fork, packages the Realtek OTA image, and publishes a **pre-release** (the build is not yet hardware-verified) with these assets:

- `*-keychron_v6_ultra.bin` / `.hex`: the raw compiled image.
- `*-keychron_v6_ultra_ota_MP.bin`: the Realtek MP/CFU image to flash via `cfudownloadtool`.
- a `.sha256` for each.

```bash
git tag ultra-v1.0.0
git push origin ultra-v1.0.0
```

Releases stay marked experimental until a build has been flashed and confirmed on real hardware.
