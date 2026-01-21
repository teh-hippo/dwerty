#!/usr/bin/env bash
# Firmware workflow for Keychron V6 Max Dvorak-QWERTY
#
# Usage: ./scripts/firmware.sh [all|build|flash]
# Defaults to "all" (build + flash)

set -euo pipefail

ACTION="${1:-all}"

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
  if [[ -x /mnt/c/Windows/System32/usbipd.exe ]]; then
    echo "/mnt/c/Windows/System32/usbipd.exe"
    return 0
  fi
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

  "${PODMAN_BIN[@]}" run --rm -it \
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
  if [[ "${ACTION}" == "flash" || "${ACTION}" == "all" ]]; then
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

build_firmware() {
  local cmd='set -euo pipefail
git config --global --add safe.directory /qmk
export SKIP_GIT=1
src="/workspace/keymaps/keychron/v6_max/ansi_encoder/keymaps/$KEYMAP"
dest="/qmk/keyboards/keychron/v6_max/ansi_encoder/keymaps/$KEYMAP"
rm -rf "$dest"
mkdir -p "$(dirname "$dest")"
cp -a "$src" "$dest"

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
src="/workspace/keymaps/keychron/v6_max/ansi_encoder/keymaps/$KEYMAP"
dest="/qmk/keyboards/keychron/v6_max/ansi_encoder/keymaps/$KEYMAP"
rm -rf "$dest"
mkdir -p "$(dirname "$dest")"
cp -a "$src" "$dest"

if command -v qmk >/dev/null 2>&1; then
  (cd /qmk && qmk flash -kb "$KEYBOARD" -km "$KEYMAP")
else
  (cd /qmk && make "$KEYBOARD:$KEYMAP:flash")
fi'

  podman_run "${cmd}" --privileged --device /dev/bus/usb:/dev/bus/usb
}

if [[ "${ACTION}" == "--help" || "${ACTION}" == "-h" ]]; then
  usage
fi

if [[ "${ACTION}" != "all" && "${ACTION}" != "build" && "${ACTION}" != "flash" ]]; then
  fail "Argument must be 'all', 'build', or 'flash'."
fi

ensure_dirs

if [[ "${ACTION}" == "all" || "${ACTION}" == "flash" ]]; then
  ensure_usbipd_attached
fi

configure_podman_for_action
ensure_podman_image
ensure_qmk_repo

case "${ACTION}" in
  all)
    build_firmware
    flash_firmware
    ;;
  build)
    build_firmware
    ;;
  flash)
    flash_firmware
    ;;
esac
