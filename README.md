# Dwerty

[![Build Max Firmware](https://github.com/teh-hippo/dwerty/actions/workflows/firmware-max.yml/badge.svg)](https://github.com/teh-hippo/dwerty/actions/workflows/firmware-max.yml)
[![Build Ultra Firmware](https://github.com/teh-hippo/dwerty/actions/workflows/firmware-ultra.yml/badge.svg)](https://github.com/teh-hippo/dwerty/actions/workflows/firmware-ultra.yml)

Custom keyboard firmware that types **Dvorak** while keeping **Qwerty-position shortcuts** (Ctrl+C, Ctrl+V, and so on). The OS stays on US Qwerty and all remapping happens in firmware.

This repository holds two firmwares for two keyboards:

| Directory | Keyboard | Firmware | Status |
|-----------|----------|----------|--------|
| [`max/`](max/) | Keychron V6 Max | QMK | Shipping |
| [`ultra/`](ultra/) | Keychron V6 Ultra 8K | ZMK | Spike |

Both deliver the same idea, the "Dwerty" behaviour: the base layer types Dvorak, but holding (or one-shotting) Ctrl, Alt or Win sends the key in its Qwerty physical position, so shortcuts stay in muscle memory. Shift is excluded, so shifted letters still type Dvorak.

## Why two firmwares

The V6 Max runs QMK; the V6 Ultra runs ZMK on a Realtek RTL8762G. They share no toolchain, so each lives in its own self-contained directory with its own build scripts, tests and README.

- **`max/`** reproduces the behaviour in QMK via `process_record_user` interception. See [`max/README.md`](max/README.md).
- **`ultra/`** reproduces it in ZMK via per-key `&mod_morph` behaviours with `keep-mods`. See [`ultra/README.md`](ultra/README.md).

## Quick start

```bash
# QMK (V6 Max)
cd max && ./scripts/firmware.sh build

# ZMK (V6 Ultra) — build and virtual tests, no hardware required
cd ultra && ./scripts/build.sh && ./scripts/test.sh
```

## Releases

Each keyboard is released independently from a Git tag that shares one Dwerty project version: `max-v<x.y.z>` for the V6 Max and `ultra-v<x.y.z>` for the V6 Ultra. The Dwerty version is our own and does not have to match the Keychron firmware version each board reports. Pre-built binaries are attached to the [Releases](../../releases) page; the V6 Ultra builds are experimental until verified on hardware.
