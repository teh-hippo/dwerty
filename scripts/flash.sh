#!/usr/bin/env bash
set -euo pipefail

QMK_DIR="${QMK_DIR:-$HOME/qmk_firmware}"
KEYBOARD="keychron/v6_max/ansi_encoder"
KEYMAP="dvorak_qwerty"

if [[ ! -d "${QMK_DIR}" ]]; then
  echo "QMK_DIR not found: ${QMK_DIR}" >&2
  exit 1
fi

echo "Set the keyboard to Cable mode and hold Esc while plugging in to enter bootloader."
read -r -p "Press Enter to flash..." _

if command -v qmk >/dev/null 2>&1; then
  (cd "${QMK_DIR}" && qmk flash -kb "${KEYBOARD}" -km "${KEYMAP}")
else
  (cd "${QMK_DIR}" && make "${KEYBOARD}:${KEYMAP}:flash")
fi
