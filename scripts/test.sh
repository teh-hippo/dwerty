#!/usr/bin/env bash
# Test script for Keychron V6 Max Dvorak-QWERTY keymap
#
# Usage:
#   ./scripts/test.sh                   # Run all tests
#   ./scripts/test.sh --unit            # Run unit tests only
#   ./scripts/test.sh --integration     # Run integration tests only
#   ./scripts/test.sh --build           # Run local QMK build verification
#   ./scripts/test.sh --lint            # Run linting checks
#   ./scripts/test.sh --help            # Show this help

set -euo pipefail

TEST_TYPE="all"

usage() {
  sed -n '2,12p' "$0" | sed 's/^# \?//'
  exit 0
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
  ./scripts/firmware.sh local build
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
