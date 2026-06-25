#!/usr/bin/env bash
# Firmware workflow for Keychron V6 Max Dvorak-QWERTY
#
# Usage: ./scripts/firmware.sh [all|build|flash|flash-release [tag]]
# Defaults to "all" (build + flash). flash-release downloads a GitHub release
# .bin (latest max-v* tag by default) with gh and flashes it; no local build.

set -euo pipefail

ACTION="${1:-all}"
RELEASE_TAG="${2:-}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

CACHE_DIR="${ROOT_DIR}/.cache"
QMK_DIR="${CACHE_DIR}/qmk_keychron"
BUILD_DIR="${ROOT_DIR}/build"

KEYBOARD="keychron/v6_max/ansi_encoder"
KEYMAP="dvorak_qwerty"

QMK_REPO="https://github.com/Keychron/qmk_firmware.git"
QMK_BRANCH="wireless_playground"

IMAGE_NAME="localhost/dwerty-qmk"
CONTAINERFILE="${ROOT_DIR}/Containerfile"
IMAGE_HASH_FILE="${CACHE_DIR}/podman-image.sha256"
PODMAN_BIN=(podman)
PODMAN_USERNS=(--userns=keep-id)
PODMAN_BUILD_NET=()
PODMAN_RUN_NET=()
HOST_UID="$(id -u)"
HOST_GID="$(id -g)"
HOST_CHOWN=0

usage() {
  sed -n '2,6p' "$0" | sed 's/^# \?//'
  exit 0
}

fail() {
  echo "$1" >&2
  exit 1
}

is_wsl() {
  grep -qi microsoft /proc/version 2>/dev/null || [[ -n "${WSL_INTEROP:-}" ]] || [[ -n "${WSL_DISTRO_NAME:-}" ]]
}

usbipd_path() {
  if command -v usbipd.exe >/dev/null 2>&1; then
    command -v usbipd.exe
    return 0
  fi
  local candidate
  for candidate in \
    "/mnt/c/Program Files/usbipd-win/usbipd.exe" \
    "/mnt/c/Windows/System32/usbipd.exe"; do
    if [[ -x "${candidate}" ]]; then
      echo "${candidate}"
      return 0
    fi
  done
  return 1
}

usbipd_bootloader_entry() {
  local usbipd_bin="$1"

  "${usbipd_bin}" list 2>/dev/null | awk '
    function state_from_line(line) {
      if (line ~ /Not shared/) return "Not shared";
      if (line ~ /Attached/) return "Attached";
      if (line ~ /Shared/) return "Shared";
      return "";
    }
    /STM32[[:space:]]+BOOTLOADER/ {
      bus=$1;
      state=state_from_line($0);
      if (state != "") { print bus "|" state; exit }
      found=1;
      next;
    }
    found {
      state=state_from_line($0);
      if (state != "") { print bus "|" state; exit }
      if ($1 ~ /^[0-9]+-[0-9]+$/) { print bus "|Unknown"; exit }
    }
  '
}

ensure_usbipd_attached() {
  if ! is_wsl; then
    return 0
  fi

  local usbipd_bin
  if ! usbipd_bin=$(usbipd_path); then
    echo "usbipd.exe not available; skipping WSL attach check." >&2
    return 0
  fi

  while true; do
    local entry busid state
    entry=$(usbipd_bootloader_entry "${usbipd_bin}")
    if [[ -z "${entry}" ]]; then
      echo "Keyboard not detected. Hold Esc while plugging in USB to enter bootloader mode." >&2
      sleep 2
      continue
    fi

    busid="${entry%%|*}"
    state="${entry##*|}"

    if [[ "${state}" == "Attached" ]]; then
      echo "usbipd: STM32 BOOTLOADER attached at ${busid}." >&2
      return 0
    fi
    if [[ "${state}" == "Shared" ]]; then
      echo "usbipd: STM32 BOOTLOADER shared at ${busid}; attaching..." >&2
      if "${usbipd_bin}" attach --wsl --busid "${busid}"; then
        sleep 1
      else
        echo "usbipd: attach failed; waiting for device to be attached..." >&2
        sleep 2
      fi
      continue
    fi

    if [[ "${state}" == "Not shared" ]]; then
      echo "usbipd: STM32 BOOTLOADER not shared. Run 'usbipd bind --busid ${busid}' in Windows Admin PowerShell." >&2
    else
      echo "usbipd: STM32 BOOTLOADER detected (state: ${state}); waiting..." >&2
    fi
    sleep 2
  done
}

ensure_dirs() {
  mkdir -p "${CACHE_DIR}"
  mkdir -p "${BUILD_DIR}"
}

ensure_podman_image() {
  local current_hash
  current_hash=$(sha256sum "${CONTAINERFILE}" | awk '{print $1}')

  if "${PODMAN_BIN[@]}" image exists "${IMAGE_NAME}" 2>/dev/null; then
    if [[ -f "${IMAGE_HASH_FILE}" ]]; then
      local cached_hash
      cached_hash=$(cat "${IMAGE_HASH_FILE}")
      if [[ "${cached_hash}" == "${current_hash}" ]]; then
        return
      fi
    fi
  fi

  "${PODMAN_BIN[@]}" build "${PODMAN_BUILD_NET[@]}" -t "${IMAGE_NAME}" -f "${CONTAINERFILE}" "${ROOT_DIR}"
  echo "${current_hash}" > "${IMAGE_HASH_FILE}"
}

podman_run() {
  local cmd="$1"
  local extra_args=("${@:2}")

  # Allocate a TTY only when attached to one (keeps interactive use working,
  # but allows non-interactive/CI runs without "the input device is not a TTY").
  local tty_args=()
  if [[ -t 0 && -t 1 ]]; then
    tty_args=(-it)
  fi

  "${PODMAN_BIN[@]}" run --rm "${tty_args[@]}" \
    "${PODMAN_RUN_NET[@]}" \
    "${PODMAN_USERNS[@]}" \
    -e QMK_DIR="/qmk" \
    -e KEYBOARD="${KEYBOARD}" \
    -e KEYMAP="${KEYMAP}" \
    -e QMK_REPO="${QMK_REPO}" \
    -e QMK_BRANCH="${QMK_BRANCH}" \
    -e HOST_UID="${HOST_UID}" \
    -e HOST_GID="${HOST_GID}" \
    -e HOST_CHOWN="${HOST_CHOWN}" \
    -v "${ROOT_DIR}:/workspace:Z" \
    -v "${QMK_DIR}:/qmk:Z" \
    -w /workspace \
    "${extra_args[@]}" \
    "${IMAGE_NAME}" \
    /bin/bash -lc "${cmd}"
}

configure_podman_for_action() {
  if [[ "${ACTION}" == "flash" || "${ACTION}" == "all" || "${ACTION}" == "flash-release" ]]; then
    if [[ "${EUID}" -ne 0 ]] && command -v sudo >/dev/null 2>&1; then
      PODMAN_BIN=(sudo podman)
      HOST_CHOWN=1
    else
      PODMAN_BIN=(podman)
    fi
    PODMAN_USERNS=()
    PODMAN_BUILD_NET=(--network=host)
    PODMAN_RUN_NET=(--network=host)
  else
    PODMAN_BIN=(podman)
    PODMAN_USERNS=(--userns=keep-id)
    HOST_CHOWN=0
    PODMAN_BUILD_NET=()
    PODMAN_RUN_NET=()
  fi
}

ensure_qmk_repo() {
  mkdir -p "${QMK_DIR}"

  local cmd='set -euo pipefail
git config --global --add safe.directory /qmk
if [[ ! -d /qmk/.git ]]; then
  rm -rf /qmk/*
  git clone "$QMK_REPO" /qmk
fi

git -C /qmk remote set-url origin "$QMK_REPO"
git -C /qmk fetch origin --tags
git -C /qmk checkout "$QMK_BRANCH"
git -C /qmk reset --hard "origin/$QMK_BRANCH"
git -C /qmk clean -fdx
git -C /qmk submodule update --init --recursive

if [[ ! -f /qmk/keyboards/keychron/v6_max/info.json ]]; then
  echo "V6 Max support not found in $QMK_REPO ($QMK_BRANCH)." >&2
  exit 1
fi'

  podman_run "${cmd}"
}

KEYBOARD_RULES="/qmk/keyboards/keychron/v6_max/rules.mk"
KEYBOARD_CONFIG="/qmk/keyboards/keychron/v6_max/config.h"
KEYBOARD_INFO="/qmk/keyboards/keychron/v6_max/info.json"

# Prepare the QMK tree: copy keymap and apply patches that Keychron added to
# V3 Max (8b525cb770) but not V6 Max yet.
#
# 1. SNAP_CLICK_ENABLE and KEYCHRON_RGB_ENABLE must be set in the keyboard
#    rules.mk BEFORE the include keychron_common.mk line because its ifeq
#    guards are evaluated inline (keymap rules.mk is too late).
#
# 2. config.h needs #include "eeconfig_kb.h" early so EECONFIG_KB_DATA_SIZE
#    is defined before eeconfig.h's #ifndef guard fires (avoids -Werror
#    redefinition), and EECONFIG_SIZE_CUSTOM_RGB is visible for RGB guards.
#
# 3. info.json debounce_type must be "custom" so keychron_common.mk pulls in
#    debounce/debounce.mk (-DDYNAMIC_DEBOUNCE_ENABLE). That is what makes the
#    firmware advertise FEATURE_DYNAMIC_DEBOUNCE over raw HID, which is the only
#    way the Keychron Launcher shows the "bounce time" Advanced Mode control.
#    Default algorithm stays sym_eager_pk and the default time stays DEBOUNCE.
prepare_qmk_tree() {
  local cmd='set -euo pipefail
git config --global --add safe.directory /qmk
export SKIP_GIT=1
src="/workspace/keymaps/keychron/v6_max/ansi_encoder/keymaps/$KEYMAP"
dest="/qmk/keyboards/keychron/v6_max/ansi_encoder/keymaps/$KEYMAP"
rm -rf "$dest"
mkdir -p "$(dirname "$dest")"
cp -a "$src" "$dest"

rules="'"${KEYBOARD_RULES}"'"
if ! grep -q "SNAP_CLICK_ENABLE" "$rules"; then
  sed -i "1i SNAP_CLICK_ENABLE=yes\nKEYCHRON_RGB_ENABLE=yes\n" "$rules"
fi

config="'"${KEYBOARD_CONFIG}"'"
if ! grep -q "eeconfig_kb.h" "$config"; then
  sed -i "/#pragma once/a\\
#include \"eeconfig_kb.h\"" "$config"
fi

info="'"${KEYBOARD_INFO}"'"
if grep -q "\"debounce_type\": \"sym_eager_pk\"" "$info"; then
  sed -i "s/\"debounce_type\": \"sym_eager_pk\"/\"debounce_type\": \"custom\"/" "$info"
fi'

  podman_run "${cmd}"
}

build_firmware() {
  local cmd='set -euo pipefail
git config --global --add safe.directory /qmk
export SKIP_GIT=1

if command -v qmk >/dev/null 2>&1; then
  (cd /qmk && qmk compile -kb "$KEYBOARD" -km "$KEYMAP")
else
  (cd /qmk && make "$KEYBOARD:$KEYMAP")
fi

mkdir -p /workspace/build
bin_path="/qmk/.build/keychron_v6_max_ansi_encoder_${KEYMAP}.bin"
hex_path="/qmk/.build/keychron_v6_max_ansi_encoder_${KEYMAP}.hex"

if [[ -f "$bin_path" ]]; then
  cp -f "$bin_path" /workspace/build/
fi
if [[ -f "$hex_path" ]]; then
  cp -f "$hex_path" /workspace/build/
fi

if [[ "$HOST_CHOWN" == "1" ]]; then
  chown -R "$HOST_UID:$HOST_GID" /workspace/build || true
fi'

  podman_run "${cmd}"
}

flash_firmware() {
  local cmd='set -euo pipefail
git config --global --add safe.directory /qmk
export SKIP_GIT=1

if command -v qmk >/dev/null 2>&1; then
  (cd /qmk && qmk flash -kb "$KEYBOARD" -km "$KEYMAP")
else
  (cd /qmk && make "$KEYBOARD:$KEYMAP:flash")
fi'

  podman_run "${cmd}" --privileged --device /dev/bus/usb:/dev/bus/usb
}

# Resolve the release tag to flash: the explicit second argument, or the newest
# max-v* GitHub release (gh lists newest first).
resolve_release_tag() {
  if [[ -n "${RELEASE_TAG}" ]]; then
    echo "${RELEASE_TAG}"
    return 0
  fi
  gh release list -L 50 --json tagName \
    -q 'map(.tagName) | map(select(startswith("max-v"))) | .[0]' 2>/dev/null
}

# Deploy a pre-built GitHub release: download the .bin with gh, verify its
# SHA256, then DFU-flash it. No local QMK build or container compile required.
flash_release() {
  command -v gh >/dev/null 2>&1 || \
    fail "gh (GitHub CLI) is required for flash-release. Install gh, or download the .bin from the Releases page and flash with QMK Toolbox."

  local tag
  tag=$(resolve_release_tag)
  [[ -n "${tag}" ]] || fail "Could not resolve a max-v* release tag. Pass one: ./scripts/firmware.sh flash-release max-vX.Y.Z"

  local bin_name="${tag}-keychron_v6_max.bin"
  local bin="${BUILD_DIR}/${bin_name}"

  echo "Downloading ${tag} from GitHub Releases..." >&2
  gh release download "${tag}" \
    --pattern "${bin_name}" \
    --pattern "${bin_name}.sha256" \
    --dir "${BUILD_DIR}" --clobber \
    || fail "gh release download failed for ${tag}."
  [[ -f "${bin}" ]] || fail "Expected asset ${bin_name} not found in release ${tag}."

  local expected actual
  expected=$(awk '{print $1}' "${bin}.sha256")
  actual=$(sha256sum "${bin}" | awk '{print $1}')
  [[ "${expected}" == "${actual}" ]] \
    || fail "SHA256 mismatch for ${bin_name} (expected ${expected}, got ${actual})."
  echo "Verified ${bin_name} (sha256 OK)." >&2

  ensure_usbipd_attached

  local cmd='set -euo pipefail
bin="/workspace/build/'"${bin_name}"'"
echo "Flashing $bin via dfu-util (stm32-dfu)..."
dfu-util -a 0 -d 0483:DF11 -s 0x08000000:leave -D "$bin"'

  podman_run "${cmd}" --privileged --device /dev/bus/usb:/dev/bus/usb
}

if [[ "${ACTION}" == "--help" || "${ACTION}" == "-h" ]]; then
  usage
fi

if [[ "${ACTION}" != "all" && "${ACTION}" != "build" && "${ACTION}" != "flash" && "${ACTION}" != "flash-release" ]]; then
  fail "Argument must be 'all', 'build', 'flash', or 'flash-release'."
fi

ensure_dirs

if [[ "${ACTION}" == "all" || "${ACTION}" == "flash" ]]; then
  ensure_usbipd_attached
fi

configure_podman_for_action
ensure_podman_image

case "${ACTION}" in
  all)
    ensure_qmk_repo
    prepare_qmk_tree
    build_firmware
    flash_firmware
    ;;
  build)
    ensure_qmk_repo
    prepare_qmk_tree
    build_firmware
    ;;
  flash)
    ensure_qmk_repo
    prepare_qmk_tree
    flash_firmware
    ;;
  flash-release)
    flash_release
    ;;
esac
