#!/usr/bin/env bash
set -euo pipefail

QMK_DIR="${QMK_DIR:-}"
QMK_REPO="${QMK_REPO:-https://github.com/Keychron/qmk_firmware.git}"
QMK_BRANCH="${QMK_BRANCH:-wireless_playground}"
TEMP_QMK=""

cleanup() {
  if [[ -n "${TEMP_QMK}" ]]; then
    rm -rf "${TEMP_QMK}"
  fi
}

if [[ -z "${QMK_DIR}" ]]; then
  TEMP_QMK="$(mktemp -d)"
  trap cleanup EXIT
  git clone --depth 1 --branch "${QMK_BRANCH}" "${QMK_REPO}" "${TEMP_QMK}"
  QMK_DIR="${TEMP_QMK}"
fi

(cd "${QMK_DIR}" && git submodule update --init --recursive)

if [[ ! -f "${QMK_DIR}/keyboards/keychron/v6_max/info.json" ]]; then
  echo "V6 Max support not found in QMK_DIR: ${QMK_DIR}" >&2
  exit 1
fi

QMK_DIR="${QMK_DIR}" ./scripts/install_keymap.sh
QMK_DIR="${QMK_DIR}" ./scripts/build.sh
