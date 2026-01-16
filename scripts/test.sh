#!/usr/bin/env bash
# Test script for Keychron V6 Max Dvorak-QWERTY keymap
#
# Usage:
#   ./scripts/test.sh                   # Run all tests
#   ./scripts/test.sh --unit            # Run unit tests only
#   ./scripts/test.sh --integration     # Run integration tests only
#   ./scripts/test.sh --build           # Run QMK build verification test
#   ./scripts/test.sh --lint            # Run linting checks
#   ./scripts/test.sh --help            # Show this help
#
# Environment variables:
#   QMK_DIR        - Path to QMK firmware (default: $HOME/qmk_firmware)
#   QMK_REPO       - QMK repository URL (for --build test)
#   QMK_BRANCH     - QMK branch (for --build test)

set -euo pipefail

QMK_DIR="${QMK_DIR:-}"
QMK_REPO="${QMK_REPO:-https://github.com/Keychron/qmk_firmware.git}"
QMK_BRANCH="${QMK_BRANCH:-wireless_playground}"
TEMP_QMK=""

TEST_TYPE="all"

usage() {
  sed -n '2,12p' "$0" | sed 's/^# \?//'
  exit 0
}

cleanup() {
  if [[ -n "${TEMP_QMK}" && -d "${TEMP_QMK}" ]]; then
    rm -rf "${TEMP_QMK}"
  fi
}

run_unit_tests() {
  echo "Running unit tests..."
  python -m unittest discover -s tests -p "test_shortcuts_*.py"
}

run_integration_tests() {
  echo "Running integration tests..."
  python -m unittest discover -s tests -p "test_integration_*.py"
}

run_build_test() {
  echo "Running QMK build verification test..."
  
  if [[ -z "${QMK_DIR}" ]]; then
    TEMP_QMK="$(mktemp -d)"
    trap cleanup EXIT
    echo "Cloning QMK from ${QMK_REPO} (${QMK_BRANCH})..."
    git clone --depth 1 --branch "${QMK_BRANCH}" "${QMK_REPO}" "${TEMP_QMK}"
    QMK_DIR="${TEMP_QMK}"
  fi
  
  echo "Updating QMK submodules..."
  (cd "${QMK_DIR}" && git submodule update --init --recursive)
  
  if [[ ! -f "${QMK_DIR}/keyboards/keychron/v6_max/info.json" ]]; then
    echo "V6 Max support not found in QMK_DIR: ${QMK_DIR}" >&2
    exit 1
  fi
  
  echo "Installing keymap..."
  QMK_DIR="${QMK_DIR}" ./scripts/install_keymap.sh
  
  echo "Building firmware..."
  QMK_DIR="${QMK_DIR}" ./scripts/build.sh
  
  echo "QMK build verification passed"
}

run_all_tests() {
  echo "Running all tests..."
  python -m unittest discover -s tests
}

# Parse arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --unit)
      TEST_TYPE="unit"
      shift
      ;;
    --integration)
      TEST_TYPE="integration"
      shift
      ;;
    --build)
      TEST_TYPE="build"
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

# Execute requested tests
case "${TEST_TYPE}" in
  unit)
    run_unit_tests
    ;;
  integration)
    run_integration_tests
    ;;
  build)
    run_build_test
    ;;
  all)
    run_all_tests
    ;;
esac

echo "All requested tests passed"
