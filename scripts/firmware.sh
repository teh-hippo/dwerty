#!/usr/bin/env bash
# Opinionated firmware workflow for Keychron V6 Max Dvorak-QWERTY
#
# Usage:
#   ./scripts/firmware.sh podman [all|build|flash]
#   ./scripts/firmware.sh local  [all|build|flash]
#
# Defaults:
#   - Action defaults to "all" when omitted.
#   - QMK cache lives in ./.cache/qmk_keychron (hard reset + clean each run).

set -euo pipefail

MODE="${1:-}"
ACTION="${2:-all}"

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
PODMAN_CMD=""
PODMAN_BIN=(podman)
PODMAN_USERNS=(--userns=keep-id)
PODMAN_BUILD_NET=()
PODMAN_RUN_NET=()
HOST_UID="$(id -u)"
HOST_GID="$(id -g)"
HOST_CHOWN=0

usage() {
  sed -n '2,12p' "$0" | sed 's/^# \?//'
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
    entry=$("${usbipd_bin}" list 2>/dev/null | awk '/STM32[[:space:]]+BOOTLOADER/ {bus=$1; getline; state=$1; print bus "|" state; exit}')
    if [[ -z "${entry}" ]]; then
      echo "Waiting for STM32 BOOTLOADER (hold Esc while plugging in USB)..." >&2
      sleep 2
      continue
    fi

    busid="${entry%%|*}"
    state="${entry##*|}"

    if [[ "${state}" == "Attached" ]]; then
      echo "usbipd: STM32 BOOTLOADER attached at ${busid}." >&2
      return 0
    fi

    echo "usbipd: STM32 BOOTLOADER detected (${state}); attaching..." >&2
    if "${usbipd_bin}" attach --wsl --busid "${busid}"; then
      sleep 1
    else
      echo "usbipd: attach failed; waiting for device to be shared/attached..." >&2
      sleep 2
    fi
  done
}

ensure_dirs() {
  mkdir -p "${CACHE_DIR}"
  mkdir -p "${BUILD_DIR}"
}

ensure_qmk_repo_local() {
  if [[ ! -d "${QMK_DIR}/.git" ]]; then
    rm -rf "${QMK_DIR}"
    git clone "${QMK_REPO}" "${QMK_DIR}"
  fi

  git -C "${QMK_DIR}" remote set-url origin "${QMK_REPO}"
  git -C "${QMK_DIR}" fetch origin --tags
  git -C "${QMK_DIR}" checkout "${QMK_BRANCH}"
  git -C "${QMK_DIR}" reset --hard "origin/${QMK_BRANCH}"
  git -C "${QMK_DIR}" clean -fdx
  git -C "${QMK_DIR}" submodule update --init --recursive

  if [[ ! -f "${QMK_DIR}/keyboards/keychron/v6_max/info.json" ]]; then
    fail "V6 Max support not found in ${QMK_REPO} (${QMK_BRANCH})."
  fi
}

install_keymap_local() {
  local src="${ROOT_DIR}/keymaps/keychron/v6_max/ansi_encoder/keymaps/${KEYMAP}"
  local dest="${QMK_DIR}/keyboards/keychron/v6_max/ansi_encoder/keymaps/${KEYMAP}"

  rm -rf "${dest}"
  mkdir -p "$(dirname "${dest}")"
  cp -a "${src}" "${dest}"
}

collect_artifacts_local() {
  local bin_path="${QMK_DIR}/.build/keychron_v6_max_ansi_encoder_${KEYMAP}.bin"
  local hex_path="${QMK_DIR}/.build/keychron_v6_max_ansi_encoder_${KEYMAP}.hex"

  if [[ -f "${bin_path}" ]]; then
    cp -f "${bin_path}" "${BUILD_DIR}/"
  fi
  if [[ -f "${hex_path}" ]]; then
    cp -f "${hex_path}" "${BUILD_DIR}/"
  fi
}

build_local() {
  if command -v qmk >/dev/null 2>&1; then
    (cd "${QMK_DIR}" && qmk compile -kb "${KEYBOARD}" -km "${KEYMAP}")
  else
    (cd "${QMK_DIR}" && make "${KEYBOARD}:${KEYMAP}")
  fi

  collect_artifacts_local
}

flash_local() {
  if command -v qmk >/dev/null 2>&1; then
    (cd "${QMK_DIR}" && qmk flash -kb "${KEYBOARD}" -km "${KEYMAP}")
  else
    (cd "${QMK_DIR}" && make "${KEYBOARD}:${KEYMAP}:flash")
  fi
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
  local extra_args=("${@}")

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
    /bin/bash -lc "${PODMAN_CMD}"
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

ensure_qmk_repo_podman() {
  mkdir -p "${QMK_DIR}"

  PODMAN_CMD='set -euo pipefail
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

  podman_run
}

build_podman() {
  PODMAN_CMD='set -euo pipefail
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

  podman_run
}

flash_podman() {
  PODMAN_CMD='set -euo pipefail
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

  podman_run --privileged --device /dev/bus/usb:/dev/bus/usb
}

if [[ "${MODE}" == "--help" || "${MODE}" == "-h" ]]; then
  usage
fi

if [[ "${MODE}" != "podman" && "${MODE}" != "local" ]]; then
  fail "First argument must be 'podman' or 'local'."
fi

if [[ "${ACTION}" != "all" && "${ACTION}" != "build" && "${ACTION}" != "flash" ]]; then
  fail "Second argument must be 'all', 'build', or 'flash'."
fi

ensure_dirs

if [[ "${ACTION}" == "all" || "${ACTION}" == "flash" ]]; then
  ensure_usbipd_attached
fi

if [[ "${MODE}" == "podman" ]]; then
  configure_podman_for_action
  ensure_podman_image
  ensure_qmk_repo_podman

  case "${ACTION}" in
    all)
      build_podman
      flash_podman
      ;;
    build)
      build_podman
      ;;
    flash)
      flash_podman
      ;;
  esac
else
  ensure_qmk_repo_local
  install_keymap_local

  case "${ACTION}" in
    all)
      build_local
      flash_local
      ;;
    build)
      build_local
      ;;
    flash)
      flash_local
      ;;
  esac
fi
