#!/usr/bin/env bash
# Package a built firmware image into the Realtek MP image and the CFU
# offer + payload folder that Keychron's cfudownloadtool flashes.
#
# The Realtek prepend_header and PackCli tools are x86_64-only, so on an aarch64
# host (e.g. Snapdragon WSL) they run under qemu-x86_64 (apt install qemu-user).
# On an x86_64 host they run natively. PackCli is not in the Keychron fork, so
# it is fetched pinned from rtkconnectivity's public SDK and verified by SHA256.
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
FLASH_MAP="${ULTRA_DIR}/flash_map.ini"

# PackCli is Realtek's sanctioned CFU packer. It is not in the Keychron fork, so
# fetch it pinned from rtkconnectivity's public SDK and verify it by SHA256.
PACKCLI_PIN="708600d50eee2b65e425e05845933a48bea82d96"
PACKCLI_SHA256="99af5255490fb436f0047b8f18c802662ebebbe73c7ea9c6ffb8ceebe6696d1a"
PACKCLI_URL="https://raw.githubusercontent.com/rtkconnectivity/rtl87x2g_sdk/${PACKCLI_PIN}/tools/PackCli/PackCli"
PACKCLI="${ULTRA_DIR}/.cache/packcli/PackCli"

[[ -f "${BIN}" ]]       || { echo "Missing ${BIN}; run scripts/build.sh first." >&2; exit 1; }
[[ -x "${TOOL}" ]]      || { echo "Missing RTK tool ${TOOL}; run scripts/build.sh first." >&2; exit 1; }
[[ -f "${FLASH_MAP}" ]] || { echo "Missing ${FLASH_MAP} (CFU flash layout)." >&2; exit 1; }

# Choose a runner: native on x86_64, qemu-x86_64 elsewhere.
RUN=()
if [[ "$(uname -m)" != "x86_64" ]]; then
  if ! command -v qemu-x86_64 >/dev/null 2>&1; then
    echo "Realtek's prepend_header and PackCli tools are x86_64-only and this host is $(uname -m)." >&2
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

# Fetch + verify PackCli (cached under .cache/packcli), then pack the MP image
# into the CFU offer + payload folder that cfudownloadtool flashes. PackCli keys
# off the "flash map.ini" layout and an image whose name ends in -<md5>.bin; the
# version prefix comes from mp.ini.
if [[ ! -f "${PACKCLI}" ]] || ! echo "${PACKCLI_SHA256}  ${PACKCLI}" | sha256sum -c - >/dev/null 2>&1; then
  echo "Fetching PackCli (pinned ${PACKCLI_PIN})..."
  mkdir -p "$(dirname "${PACKCLI}")"
  curl -fsSL -o "${PACKCLI}" "${PACKCLI_URL}"
  echo "${PACKCLI_SHA256}  ${PACKCLI}" | sha256sum -c - \
    || { echo "PackCli SHA256 mismatch; refusing to use it." >&2; exit 1; }
  chmod +x "${PACKCLI}"
fi

mpver="$(grep -oP '^Version=\K.*' "${MPINI}" | tr -d '[:space:]')"
md5="$(md5sum "${work}/zmk_MP.bin" | awk '{print $1}')"
mkdir -p "${work}/cfu-src"
cp "${work}/zmk_MP.bin" "${work}/cfu-src/zmkImage_MP_${mpver}_0-${md5}.bin"
cp "${FLASH_MAP}"       "${work}/cfu-src/flash map.ini"
( cd "${work}" && "${RUN[@]}" "${PACKCLI}" -n 8762G -m CFU -s cfu-src -d cfu-out )

rm -rf "${OUT}/cfu"
mkdir -p "${OUT}/cfu"
cp "${work}/cfu-out/CFU/_ImgPacketFile.offer.bin"   "${OUT}/cfu/"
cp "${work}/cfu-out/CFU/_ImgPacketFile.payload.bin" "${OUT}/cfu/"

echo "Wrote:"
echo "  ${OUT}/zmk_ota.bin      (Realtek image header)"
echo "  ${OUT}/zmk_ota_MP.bin   (MP/CFU image)"
echo "  ${OUT}/cfu/             (CFU offer + payload for cfudownloadtool)"
echo
echo "Flash (Windows, voids warranty): pop the spacebar keycap and hold the"
echo "button beneath it while plugging in USB to enter DFU (enumerates as"
echo "0BDA:4762 'Keychron usb DFU'), then point cfudownloadtool at ${OUT}/cfu."
