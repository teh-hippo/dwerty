# Dwerty Ultra — Keychron V6 Ultra 8K (ZMK)

ZMK firmware for the Keychron V6 Ultra 8K that reproduces the "Dwerty" behaviour from the QMK [`max/`](../max) firmware: the base layer types Dvorak, but holding or one-shotting Ctrl/Alt/Win sends the key in its Qwerty physical position (modifier kept), so shortcuts stay in muscle memory. Shift is excluded, so shifted letters still type Dvorak.

> Status: spike. The behaviour is proven with hardware-free tests and the firmware compiles for the real board. Flashing has not been exercised on hardware (see "Flashing").

## How it works

The V6 Ultra runs ZMK on a Realtek RTL8762G. Instead of QMK's runtime `process_record_user` interception, each differing key is a ZMK [`&mod_morph`](https://zmk.dev/docs/keymaps/behaviors/mod-morph): it binds its Dvorak letter normally and its Qwerty-position letter when Ctrl/Alt/GUI is held, with `keep-mods` keeping the modifier in the output. A one-shot (`&sk`) modifier registers an explicit modifier, so it triggers the morph exactly like a held modifier.

### Layers

| Layer | Name | Description |
|-------|------|-------------|
| 0 | DWERTY | Dvorak keys + 33 `&dq_*` Qwerty-position morphs |
| 1 | QWERTY | Plain Qwerty |
| 2 | DVORAK | Plain Dvorak, no morphs |
| 3 | FN | Stock RGB/Bluetooth/media overlay + `&to 0/1/2` layout selector |

The keymap is generated from the stock shield keymap by [`scripts/gen_keymap.py`](scripts/gen_keymap.py), which keeps Keychron's preamble (their custom behaviours, macros and combos) and rewrites only the layers. Regenerate with:

```bash
python3 scripts/gen_keymap.py
```

## Build and test (two separate toolchains)

The build and the tests run against different ZMK trees, on purpose:

- **Build** the real firmware on Keychron's fork (`Keychron/zmk@rtl8762g`), board `keychron`, shield `keychron_v6_ultra_ansi`, in the `zmk-build-arm:3.5` container.
- **Test** the behaviour on upstream `zmkfirmware/zmk` `native_sim` snapshot tests, in the `zmk-build-arm:4.1` container. The fork cannot host-test because its core headers pull in the Realtek HAL (`rtl_pinmux.h`). `&mod_morph` + `keep-mods` is identical between the fork and upstream, so behaviour proven on upstream holds for the real firmware.

Both need [Podman](https://podman.io). Each toolchain is set up once into `.cache/` (gitignored); the first run downloads Zephyr and is slow.

```bash
./scripts/build.sh          # compile the real firmware -> ultra/build/zmk.{elf,hex,bin}
./scripts/build.sh --clean  # discard the cached fork workspace and start fresh

./scripts/test.sh                       # run all behaviour tests
./scripts/test.sh dvorak-qwerty         # run one test directory
```

### Tests

`tests/dvorak-qwerty/` holds ZMK `native_sim` snapshot tests that assert the exact HID output:

- `1-dvorak-and-ctrl-qwerty` — tap types Dvorak; Ctrl+tap sends Ctrl+Qwerty; Shift+tap stays Dvorak.
- `2-oneshot-ctrl-qwerty` — a sticky (`&sk`) Ctrl still morphs the next key to its Qwerty position.

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
