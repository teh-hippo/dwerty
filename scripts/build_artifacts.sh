#!/usr/bin/env bash
set -euo pipefail

QMK_DIR="${QMK_DIR:-$HOME/qmk_firmware}"
BUILD_DIR="${BUILD_DIR:-$(pwd)/build}"
KEYBOARD="keychron/v6_max/ansi_encoder"
KEYMAP="dvorak_qwerty"

if [[ ! -d "${QMK_DIR}" ]]; then
  echo "QMK_DIR not found: ${QMK_DIR}" >&2
  exit 1
fi

mkdir -p "${BUILD_DIR}"

QMK_DIR="${QMK_DIR}" ./scripts/build.sh

BIN_PATH="${QMK_DIR}/.build/keychron_v6_max_ansi_encoder_${KEYMAP}.bin"
HEX_PATH="${QMK_DIR}/.build/keychron_v6_max_ansi_encoder_${KEYMAP}.hex"

if [[ -f "${BIN_PATH}" ]]; then
  cp -f "${BIN_PATH}" "${BUILD_DIR}/"
  echo "Copied $(basename "${BIN_PATH}") to ${BUILD_DIR}"
fi

if [[ -f "${HEX_PATH}" ]]; then
  cp -f "${HEX_PATH}" "${BUILD_DIR}/"
  echo "Copied $(basename "${HEX_PATH}") to ${BUILD_DIR}"
fi

if [[ ! -f "${BIN_PATH}" && ! -f "${HEX_PATH}" ]]; then
  echo "Build artifacts not found under ${QMK_DIR}/.build" >&2
  exit 1
fi
