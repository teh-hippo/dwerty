# Dwerty Ultra — Keychron V6 Ultra 8K (ZMK)

[![Build Ultra Firmware](https://github.com/teh-hippo/dwerty/actions/workflows/firmware-ultra.yml/badge.svg)](https://github.com/teh-hippo/dwerty/actions/workflows/firmware-ultra.yml)

ZMK firmware for the Keychron V6 Ultra 8K that reproduces the "Dwerty" behaviour from the QMK [`max/`](../max) firmware: the base layer types Dvorak, but holding or one-shotting Ctrl/Alt/Win sends the key in its Qwerty physical position (modifier kept), so shortcuts stay in muscle memory. Shift is excluded, so shifted letters still type Dvorak.

> Status: the firmware has been flashed and functionally checked on a V6 Ultra. CI builds the real target and runs pinned host simulations, but it does not exercise the keyboard, receiver, radio or USB transport.

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

Live default-layer changes used to resolve a held key's release on the new default layer. [`patches/0003-preserve-press-layer-on-release.patch`](patches/0003-preserve-press-layer-on-release.patch) snapshots the press-time default alongside the active layers, so Fn+Z cannot misroute a morph release and moving the Mac/Win slide while Alt or Command is held cannot leave the old modifier registered. This defect cannot explain the recorded Ctrl incident: it creates no modifier-down events, and both Ctrl bindings are identical on every base layer.

The Keychron 2.4 GHz PPT queue also discarded both the oldest queued report and the new report when full. [`patches/0004-ppt-queue-preserve-newest.patch`](patches/0004-ppt-queue-preserve-newest.patch) serialises the ring-buffer operations, then discards the oldest entry and inserts the latest state. This follows the fork's BLE policy of retaining the latest report, while remaining safe for the PPT timer consumer. This is generic transport hardening, not evidence that queue saturation caused a recorded field incident.

An opt-in diagnostic build is provided by [`patches/0005-diagnostic-trace.patch`](patches/0005-diagnostic-trace.patch). It records raw matrix transitions, debounced events, press-time layer state, modifier reference counts, HID reports, endpoint changes and PPT queue/send results in a RAM ring. The trace can be dumped through the existing Launcher raw HID interface over USB or 2.4 GHz, with an optional independent UART2 stream. It is compiled out of release firmware. See [`DIAGNOSTICS.md`](DIAGNOSTICS.md) for collection commands and the hardware proof plan.

The keymap is generated from the stock shield keymap by [`scripts/gen_keymap.py`](scripts/gen_keymap.py), which keeps Keychron's preamble (their custom behaviours, macros and combos) and rewrites only the layers and the toggle combo. Regenerate with:

```bash
python3 scripts/gen_keymap.py
```

## Build and test (two separate toolchains)

The build and the tests run against different ZMK trees, on purpose:

- **Build** the real firmware on Keychron's fork (`Keychron/zmk@rtl8762g`, pinned to commit `101a23c`), board `keychron`, shield `keychron_v6_ultra_ansi`, in the `zmk-build-arm:3.5` container. The build applies all patches in [`patches/`](patches) onto the fork's `app/src/` idempotently.
- **Test** against upstream ZMK commit `931a36f`, the pinned fork's upstream merge base, in the `zmk-build-arm:4.1` container. At that revision, `behavior_mod_morph.c` and `zmk_keymap_position_state_changed()` are byte-identical to the pinned fork. The source check enforces that provenance before the host simulation runs. The fork itself cannot host-test because its core headers pull in the Realtek HAL (`rtl_pinmux.h`).

Both need [Podman](https://podman.io), or Docker if you set `DWERTY_CONTAINER_ENGINE=docker` (CI uses Docker). Each toolchain is set up once into `.cache/` (gitignored); the first run downloads Zephyr and is slow.

```bash
./scripts/build.sh          # compile the real firmware -> ultra/build/zmk.{elf,hex,bin}
./scripts/build.sh --clean  # discard the cached fork workspace and start fresh
./scripts/build.sh --diagnostics       # ring trace -> ultra/build/diagnostics/
./scripts/build.sh --diagnostics-uart  # ring + UART2 -> ultra/build/diagnostics-uart/

./scripts/test.sh                       # run all behaviour tests
./scripts/test.sh dvorak-qwerty         # run one test directory
```

### Tests

`tests/dvorak-qwerty/` holds ZMK host-simulation snapshots that assert the exact HID output, plus host-side parity and source-invariant checks:

- `parity_dq.py` — asserts the 33 Dvorak->Qwerty pairs match `max/` exactly, so the two firmwares never drift.
- `source_invariants.py` — proves the tested mod-morph and release-routing sources match the pinned fork base, applies every patch to the exact fork, and executes the patched PPT overflow function in a C harness.
- `1-dvorak-and-ctrl-qwerty` — tap types Dvorak; Ctrl+tap sends Ctrl+Qwerty; Shift+tap stays Dvorak.
- `2-oneshot-ctrl-qwerty` — a sticky (`&sk`) Ctrl still morphs the next key to its Qwerty position.
- `3-win-overlay-preserves-morph` — with the Mac/Win slide held to the Win Dwerty base, Ctrl+tap still sends Ctrl+Qwerty while the modifier position swaps Mac→Windows.
- `4-layout-toggle-switches-base` — the standard layout selector (`&to`) flips the base so the same key types Dvorak then Qwerty, proving the layer ordering.
- `5-default-toggle-releases-morph` — a held morph is released on its press-time layer when Fn+Z changes the default, and the morph remains usable.
- `6-slide-change-releases-alt` — Mac Alt releases correctly even if the Mac/Win default changes while it is held.
- `7-slide-change-releases-ctrl` — Ctrl, whose binding is identical across OS halves, remains releasable across the same change.

The host tests reproduce the two live default-layer mutations with test-only `&to` sentinels. They execute the byte-identical upstream release-routing and mod-morph code with the production release fix applied. Settings persistence, GPIO timing, PPT scheduling, the Realtek radio stack and dongle firmware remain outside host-simulation coverage.

## Incident capture

A diagnostics build keeps a 1024-record RAM ring of matrix, keymap, modifier, HID and PPT events, readable over the Launcher raw HID interface. `scripts/capture-incident.sh` freezes that ring, saves it as a `.jsonl` trace beside a `.txt` metadata file, then re-arms the ring and detaches the keyboard from WSL.

Records exist in two protocol versions, and `protocol_version` in the capture header says which the firmware wrote. Protocol 1 is a fixed 12-byte record. Protocol 2 packs the same fields into 7 bytes by dropping the stored sequence, which a ring position already determines, and by replacing the absolute uptime with an 11-bit delta, because 77% of consecutive records share a millisecond. Both decode to identical JSON, so a capture reads the same either way.

Timing survives a wrapped ring. Every 64 records, and whenever a delta will not fit, the firmware stores a `time_skip` record holding an absolute uptime, so any retained window contains an anchor. Deltas travel with their own record, so one anchor dates a window forwards and backwards. An anchor states whether the delta it displaced was preserved; where it was not, a record that cannot be dated is marked `uptime_unknown` rather than being given a wrong time.

The firmware header's `count` and `raw_slots` count raw ring slots. Protocol 2
consumes `time_skip` anchors while decoding, so `decoded_records` can be
smaller. A complete capture satisfies
`raw_slots = decoded_records + time_skip_records`. `validate` checks that
relationship, absolute sequence coverage and unknown-timestamp accounting.

```bash
./scripts/capture-incident.sh                       # freeze, save, re-arm, detach
./scripts/diagnostics.py validate CAPTURE.jsonl     # protocol-aware completeness check
./scripts/diagnostics.py analyse CAPTURE.jsonl      # summary and anomalies
./scripts/diagnostics.py analyse --presses CAPTURE.jsonl
./scripts/diagnostics.py schema                     # what a capture's fields mean
```

`schema` emits a machine-readable description of the record layouts, every event and its fields, the summary shape, the anomaly meanings and the trace's limits. It is what lets a capture be read without this source, and each capture's `.txt` records the command that produces it.

`analyse` names every position from [`config/keychron_v6_ultra_ansi.keymap`](config/keychron_v6_ultra_ansi.keymap) using the layer the firmware recorded, so a trace reads as bindings rather than matrix coordinates. It reports the capture window in wall-clock time, derived from the device uptime and the host clock at the freeze, which is what lets a firmware trace be lined up against a host-side log.

The ring holds roughly 60 keystrokes, so it must be frozen before anything else is typed. `overwritten` in the summary counts the records already lost.

The summary counts presses and HID reports. A correct press produces exactly one report on its press edge and one on its release, which is what separates a keyboard fault from a host one: if the firmware emitted one report for a key but the host received several characters, the extra characters did not come from the keyboard. These faults are reported by name:

| Anomaly | Meaning |
| --- | --- |
| `contact_bounce_absorbed` | The switch bounced and the debouncer filtered it. Hardware wear, no output error. |
| `repeat_without_raw_release` | A debounced repeat arrived while the raw matrix still read closed, which no real second press can produce. |
| `press_without_release` | A position was pressed twice with no release routed between. |
| `release_without_press` | A release was routed for a position that was not held, with no overwritten press explaining it. |
| `modifier_error` | The firmware's modifier refcount underflowed. |
| `kscan_drop` | The scan queue discarded an event. |
| `transport_error` | A PPT queue, PPT transmit or HID send stage reported an error or discard. |

For a modifier latch the summary carries the decisive fields directly. `peak_modifiers` is the most modifiers the keyboard ever placed in a single report, `longest_modifier_hold` is the longest any one modifier stayed set, and `at_freeze.modifiers` lists those still set when recording stopped. A host showing several modifiers held while the keyboard's own peak is one or none did not get them from the keyboard.

The firmware freezes the ring itself in two cases, and `freeze_reason` says which:

| Reason | Trigger |
| --- | --- |
| `suspicious_modifiers` | A report carried five or more modifiers. Four is a chord a person can hold, so it is not treated as suspicious on its own. Eight further records are kept before stopping, preserving the run-up. |
| `modifier_held` | A modifier stayed set for `CONFIG_DWERTY_DIAGNOSTICS_MODIFIER_HOLD_MS`, default 10 seconds. A latch emits no further reports, so it can only be noticed on a timer. Ordinary chording holds a modifier for a couple of seconds. |

Nothing is recorded once the ring is frozen, so a capture must be taken and the ring re-armed before it can catch anything else.

`at_freeze` is where the capture stopped, not a fault. A ring frozen on five modifiers necessarily reports five modifiers held. Judge it by `held_ms`: a latch runs for tens of seconds, an ordinary chord for a few hundred milliseconds. `truncated_releases` are likewise a boundary effect, releases whose press was overwritten before the window opened.

The collector writes a metadata sidecar on success and failure. A validation
failure preserves the JSONL, leaves the device ring frozen, records the
validation error and detaches the selected USB device from WSL. Re-arm only
after the saved evidence has been reviewed or copied. Metadata records both
the repository commit and whether that working tree was dirty.

## The device

| Item | Value |
|------|-------|
| SoC | Realtek RTL8762G |
| Build board | `keychron` (not `rtl8762gtu_kb`; that fails on the undefined `RTK_DFU`) |
| Shield | `keychron_v6_ultra_ansi` |
| Wired USB | VID `0x3434`, PID `0x0c60`, name "Keychron V6 Ultra 8K" |
| Config tool | Keychron Launcher (WebHID); no ZMK Studio in the fork |

The 2.4 GHz receiver enumerates separately and has its own firmware. A host event attributed to a receiver PID therefore covers the keyboard PPT sender, closed Realtek transport code, RF link, dongle firmware and the dongle's USB HID path. It does not localise a fault to this keymap.

## Flashing

The running firmware exposes Realtek SC_DFU on a dedicated wired USB HID collection. This stages a prepared application image in the OTA temporary bank, verifies its CRC32 and SHA256 integrity header on-device, and only then marks it ready and reboots. It therefore provides the normal software-only update path without removing the spacebar.

The updater accepts self-built images. Reading the fork's DFU code (`app/src/dfu/tdfu.c` and `dfu_common.c`), it gates the switch on the upload CRC32, the SHA256 in the image header and the 8-byte customer name `KCZKV68K`. The only packaging snag is tooling: Realtek's `prepend_header` and `PackCli` packers are x86_64-only, so `package.sh` runs them under `qemu-x86_64` on aarch64 hosts (needs `sudo apt-get install qemu-user`).

```bash
./scripts/build.sh     # compile on the Keychron fork -> ultra/build/zmk.bin
./scripts/package.sh   # -> ultra/build/cfu/ (CFU offer + payload), plus zmk_ota*.bin
```

`package.sh` fetches Realtek's `PackCli` (pinned and SHA256-verified from rtkconnectivity's public SDK), wraps the image with `prepend_header`, and packs the `cfu/` folder (`_ImgPacketFile.offer.bin` + `.payload.bin`) that `cfudownloadtool` flashes. The `flash_map.ini` layout lives in this repo. SC_DFU must receive `zmk_ota.bin`, not raw `zmk.bin` or the CFU-specific `zmk_ota_MP.bin`.

### Software-only update

Connect the keyboard directly by USB and select wired mode. Under WSL, attach the USB device first from an elevated Windows terminal:

```powershell
usbipd list
usbipd bind --busid <BUSID>       # one-time
usbipd attach --wsl --busid <BUSID>
```

Then identify the keyboard read-only and flash the selected packaged profile:

```bash
sudo ./scripts/scdfu.py probe

./scripts/build.sh --diagnostics
./scripts/package.sh --profile diagnostics
sudo ./scripts/scdfu.py flash --profile diagnostics
```

The flasher refuses an unprepared raw image, a model other than `KCZKV68K`, an image larger than the OTA bank, unsupported DFU capabilities, or another process holding a Keychron HID node. Every 16-byte chunk is acknowledged with the keyboard's running CRC. `IMAGE_SWITCH` is sent only after the device verifies the complete staged image.

This path is hardware-verified on the V6 Ultra 8K with wired PID `3434:0C60`. An SC_DFU reboot disconnects USB, so WSL drops its usbipd attachment. Re-run:

```powershell
usbipd attach --wsl --hardware-id 3434:0c60
```

The post-flash probe should retain model `KCZKV68K` and show a new build timestamp.

### Physical recovery

The physical Realtek DFU app remains the recovery path if the application firmware cannot boot or expose SC_DFU:

1. Pop off the spacebar keycap and hold the button beneath it while plugging in the USB cable. The keyboard enters DFU and enumerates as `0BDA:4762` "Keychron usb DFU".
2. Point Keychron's `cfudownloadtool` at the `cfu` folder (locally, or the unzipped `*_cfu.zip` from a release) and download.
3. The board reboots into the new firmware.

There is no power-on key chord for the independent recovery app. It samples the dedicated `P2_5` hardware input during reset. The keymap contains an unused generic ZMK `&bootloader` behaviour, but that emits the nRF/UF2 reset reason and is not a proven RTL8762G recovery mechanism, so it is deliberately not bound.

## Releases

Releases are published per keyboard from a Git tag. The V6 Ultra uses **`ultra-v<dwerty>`** tags, where `<dwerty>` is our shared Dwerty project version (the same scheme as the V6 Max's `max-v*`). That version is our own and need not match the Keychron firmware version the board reports (currently v1.0.2, the fork's ZMK app version).

Each `ultra-v*` tag runs the behaviour tests, builds the firmware on the Keychron fork, packs the CFU folder, and publishes a release with these assets:

- `*-keychron_v6_ultra_cfu.zip`: the CFU offer + payload folder to flash with `cfudownloadtool` (see above).
- `*-keychron_v6_ultra_scdfu.bin`: the prepared application image for `scripts/scdfu.py`.
- `*-keychron_v6_ultra.bin` / `.hex`: raw build artefacts, not accepted by SC_DFU.
- `*-keychron_v6_ultra_ota_MP.bin`: the Realtek MP/CFU image.
- a `.sha256` for each.

```bash
git tag ultra-v2.2.0
git push origin ultra-v2.2.0
```
