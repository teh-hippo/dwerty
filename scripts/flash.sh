#!/usr/bin/env bash
# Flash script for Keychron V6 Max Dvorak-QWERTY keymap
#
# Usage:
#   ./scripts/flash.sh                  # Standard flash
#   ./scripts/flash.sh --easy           # Install, build, then flash (simplified workflow)
#   ./scripts/flash.sh --help           # Show this help
#
# Environment variables:
#   QMK_DIR        - Path to QMK firmware (default: $HOME/qmk_firmware)

set -euo pipefail

QMK_DIR="${QMK_DIR:-$HOME/qmk_firmware}"
KEYBOARD="keychron/v6_max/ansi_encoder"
KEYMAP="dvorak_qwerty"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

EASY_MODE=false

usage() {
  sed -n '2,10p' "$0" | sed 's/^# \?//'
  exit 0
}

flash_firmware() {
  if [[ ! -d "${QMK_DIR}" ]]; then
    echo "QMK_DIR not found: ${QMK_DIR}" >&2
    echo "Run ./scripts/setup_qmk.sh first or set QMK_DIR to your QMK checkout." >&2
    exit 1
  fi
  
  echo "Set the keyboard to Cable mode and hold Esc while plugging in to enter bootloader."
  read -r -p "Press Enter to flash..." _
  
  if command -v qmk >/dev/null 2>&1; then
    (cd "${QMK_DIR}" && qmk flash -kb "${KEYBOARD}" -km "${KEYMAP}")
  else
    (cd "${QMK_DIR}" && make "${KEYBOARD}:${KEYMAP}:flash")
  fi
}

easy_flash() {
  echo "Easy flash mode: install keymap, build, then flash"
  echo ""
  
  echo "Step 1/3: Installing keymap..."
  "${SCRIPT_DIR}/install_keymap.sh"
  echo ""
  
  echo "Step 2/3: Building firmware..."
  "${SCRIPT_DIR}/build.sh"
  echo ""
  
  echo "Step 3/3: Flashing firmware..."
  flash_firmware
}

# Parse arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --easy)
      EASY_MODE=true
      shift
      ;;
    --help|-h)
      usage
      ;;
    *)
      echo "Unknown option: $1" >&2
      echo "Use --help for usage information" >&2
      exit 1
      ;;
  esac
done

# Execute requested operation
if [[ "${EASY_MODE}" == "true" ]]; then
  easy_flash
else
  flash_firmware
fi
