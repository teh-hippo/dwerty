#!/usr/bin/env bash
# Package a built firmware image into the Realtek OTA / MP format that the
# Keychron Launcher / cfudownloadtool flashes.
#
# The Realtek prepend_header tool is x86_64-only, so on an aarch64 host (e.g.
# Snapdragon WSL) it is run under qemu-x86_64 (apt install qemu-user). On an
# x86_64 host it runs natively.
#
# Run scripts/build.sh first to produce ultra/build/zmk.bin.
# Usage: ./scripts/package.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ULTRA_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

FORK_ZMK="${ULTRA_DIR}/.cache/fork/zmk"
TOOL="${FORK_ZMK}/app/tools/prepend_header/linux-x86_64/prepend_header"
MPINI="${FORK_ZMK}/app/tools/mp.ini"
BIN="${ULTRA_DIR}/build/zmk.bin"
OUT="${ULTRA_DIR}/build"

[[ -f "${BIN}" ]]  || { echo "Missing ${BIN}; run scripts/build.sh first." >&2; exit 1; }
[[ -x "${TOOL}" ]] || { echo "Missing RTK tool ${TOOL}; run scripts/build.sh first." >&2; exit 1; }

# Choose a runner: native on x86_64, qemu-x86_64 elsewhere.
RUN=()
if [[ "$(uname -m)" != "x86_64" ]]; then
  if ! command -v qemu-x86_64 >/dev/null 2>&1; then
    echo "The Realtek prepend_header tool is x86_64-only and this host is $(uname -m)." >&2
    echo "Install an emulator: sudo apt-get install qemu-user" >&2
    exit 1
  fi
  RUN=(qemu-x86_64)
fi

work="$(mktemp -d)"
trap 'rm -rf "${work}"' EXIT
cp "${BIN}" "${work}/zmk.bin"
cp "${MPINI}" "${work}/mp.ini"

# -t app_code: application image  -m 1: image header + MP header
# -c sha256: integrity hash       -b 15: RTL8762G ic type
( cd "${work}" && "${RUN[@]}" "${TOOL}" -t app_code -p zmk.bin -m 1 -c sha256 -b 15 )

cp "${work}/zmk.bin"    "${OUT}/zmk_ota.bin"      # image-header-prepended image
cp "${work}/zmk_MP.bin" "${OUT}/zmk_ota_MP.bin"   # MP/CFU image for cfudownloadtool

echo "Wrote:"
echo "  ${OUT}/zmk_ota.bin     (Realtek image header)"
echo "  ${OUT}/zmk_ota_MP.bin  (MP/CFU image to flash via the Launcher / cfudownloadtool)"
echo
echo "On-device: hold the back-of-board button (P2_5) to enter DFU, then push"
echo "zmk_ota_MP.bin with Keychron's cfudownloadtool (Windows). Voids warranty."
