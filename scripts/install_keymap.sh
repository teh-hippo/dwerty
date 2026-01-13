#!/usr/bin/env bash
set -euo pipefail

QMK_DIR="${QMK_DIR:-$HOME/qmk_firmware}"
KEYMAP_DIR="keymaps/keychron/v6_max/ansi_encoder/keymaps/dvorak_qwerty"

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/${KEYMAP_DIR}"
DEST="${QMK_DIR}/keyboards/keychron/v6_max/ansi_encoder/keymaps/dvorak_qwerty"

if [[ ! -d "${QMK_DIR}" ]]; then
  echo "QMK_DIR not found: ${QMK_DIR}" >&2
  echo "Set QMK_DIR to your Keychron qmk_firmware checkout." >&2
  exit 1
fi

if [[ ! -d "${SRC}" ]]; then
  echo "Source keymap not found: ${SRC}" >&2
  exit 1
fi

mkdir -p "$(dirname "${DEST}")"
rm -rf "${DEST}"
cp -a "${SRC}" "${DEST}"

echo "Installed keymap to ${DEST}"
