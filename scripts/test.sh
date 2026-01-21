#!/usr/bin/env bash
set -euo pipefail

TEST_TYPE="all"

run_unit_tests() {
  echo "Running unit tests..."
  python -m unittest discover -s tests -p "test_shortcuts_*.py"
}

run_integration_tests() {
  echo "Running integration tests..."
  python -m unittest discover -s tests -p "test_integration_*.py"
}

run_all_tests() {
  echo "Running all tests..."
  python -m unittest discover -s tests
}

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
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
done

case "${TEST_TYPE}" in
  unit)
    run_unit_tests
    ;;
  integration)
    run_integration_tests
    ;;
  all)
    run_all_tests
    ;;
esac

echo "All requested tests passed"
