#!/usr/bin/env bash
# Build script for Keychron V6 Max Dvorak-QWERTY keymap
#
# Usage:
#   ./scripts/build.sh                  # Standard QMK build
#   ./scripts/build.sh --artifacts      # Build and copy artifacts to ./build/
#   ./scripts/build.sh --podman         # Build using Podman container
#   ./scripts/build.sh --help           # Show this help
#
# Environment variables:
#   QMK_DIR        - Path to QMK firmware (default: $HOME/qmk_firmware)
#   BUILD_DIR      - Path for artifact output (default: ./build)
#   IMAGE_NAME     - Podman image name (default: dwerty-qmk)
#   CONTAINERFILE  - Path to Containerfile (default: Containerfile)

set -euo pipefail

QMK_DIR="${QMK_DIR:-$HOME/qmk_firmware}"
BUILD_DIR="${BUILD_DIR:-$(pwd)/build}"
KEYBOARD="keychron/v6_max/ansi_encoder"
KEYMAP="dvorak_qwerty"
IMAGE_NAME="${IMAGE_NAME:-dwerty-qmk}"
CONTAINERFILE="${CONTAINERFILE:-Containerfile}"

ARTIFACTS=false
PODMAN=false

usage() {
  sed -n '2,10p' "$0" | sed 's/^# \?//'
  exit 0
}

build_with_podman() {
  echo "Building Podman image ${IMAGE_NAME}..."
  podman build -t "${IMAGE_NAME}" -f "${CONTAINERFILE}" .
  echo "Podman image ${IMAGE_NAME} built successfully"
}

build_firmware() {
  if [[ ! -d "${QMK_DIR}" ]]; then
    echo "QMK_DIR not found: ${QMK_DIR}" >&2
    echo "Run ./scripts/setup_qmk.sh first or set QMK_DIR to your QMK checkout." >&2
    exit 1
  fi

  echo "Building firmware: ${KEYBOARD}:${KEYMAP}"
  
  if command -v qmk >/dev/null 2>&1; then
    (cd "${QMK_DIR}" && qmk compile -kb "${KEYBOARD}" -km "${KEYMAP}")
  else
    (cd "${QMK_DIR}" && make "${KEYBOARD}:${KEYMAP}")
  fi
  
  echo "Build completed successfully"
}

collect_artifacts() {
  mkdir -p "${BUILD_DIR}"
  
  BIN_PATH="${QMK_DIR}/.build/keychron_v6_max_ansi_encoder_${KEYMAP}.bin"
  HEX_PATH="${QMK_DIR}/.build/keychron_v6_max_ansi_encoder_${KEYMAP}.hex"
  
  local copied=false
  
  if [[ -f "${BIN_PATH}" ]]; then
    cp -f "${BIN_PATH}" "${BUILD_DIR}/"
    echo "Copied $(basename "${BIN_PATH}") to ${BUILD_DIR}"
    copied=true
  fi
  
  if [[ -f "${HEX_PATH}" ]]; then
    cp -f "${HEX_PATH}" "${BUILD_DIR}/"
    echo "Copied $(basename "${HEX_PATH}") to ${BUILD_DIR}"
    copied=true
  fi
  
  if [[ "${copied}" == "false" ]]; then
    echo "Build artifacts not found under ${QMK_DIR}/.build" >&2
    exit 1
  fi
}

# Parse arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --artifacts)
      ARTIFACTS=true
      shift
      ;;
    --podman)
      PODMAN=true
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

# Execute requested operations
if [[ "${PODMAN}" == "true" ]]; then
  build_with_podman
else
  build_firmware
  
  if [[ "${ARTIFACTS}" == "true" ]]; then
    collect_artifacts
  fi
fi
