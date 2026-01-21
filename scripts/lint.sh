#!/usr/bin/env bash
# Linting script for Keychron V6 Max Dvorak-QWERTY keymap
#
# Usage:
#   ./scripts/lint.sh                   # Run all linters
#   ./scripts/lint.sh --python          # Run Python linter only
#   ./scripts/lint.sh --shell           # Run shell script linter only
#   ./scripts/lint.sh --c               # Run C code formatter check only
#   ./scripts/lint.sh --help            # Show this help
#
# Requirements:
#   - ruff (Python linting): pip install ruff
#   - shellcheck (shell script linting): apt install shellcheck
#   - clang-format (C formatting): apt install clang-format
#
# Environment variables:
#   QMK_DIR        - Path to QMK firmware (default: $HOME/qmk_firmware)

set -euo pipefail

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

QMK_DIR="${QMK_DIR:-}"
LINT_TYPE="all"
EXIT_CODE=0

usage() {
  sed -n '2,14p' "$0" | sed 's/^# \?//'
  exit 0
}

print_header() {
  echo -e "${BLUE}==>${NC} $1"
}

print_success() {
  echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
  echo -e "${YELLOW}!${NC} $1"
}

print_error() {
  echo -e "${RED}✗${NC} $1"
}

check_command() {
  if ! command -v "$1" &> /dev/null; then
    print_warning "$1 not found. Install it to enable $2 linting."
    return 1
  fi
  return 0
}

lint_python() {
  print_header "Linting Python files..."
  
  if ! check_command "ruff" "Python"; then
    print_warning "Skipping Python linting (ruff not installed)"
    return 0
  fi
  
  if ! ruff check tests/; then
    print_error "Python linting failed"
    EXIT_CODE=1
    return 1
  fi
  
  print_success "Python linting passed"
  return 0
}

lint_shell() {
  print_header "Linting shell scripts..."
  
  if ! check_command "shellcheck" "shell script"; then
    print_warning "Skipping shell script linting (shellcheck not installed)"
    return 0
  fi
  
  local scripts=(
    scripts/firmware.sh
    scripts/lint.sh
    scripts/test.sh
  )
  
  local failed=0
  for script in "${scripts[@]}"; do
    if [[ -f "$script" ]]; then
      if ! shellcheck "$script"; then
        print_error "Shell script linting failed: $script"
        failed=1
      fi
    fi
  done
  
  if [[ $failed -eq 1 ]]; then
    EXIT_CODE=1
    return 1
  fi
  
  print_success "Shell script linting passed"
  return 0
}

lint_c() {
  print_header "Checking C code formatting..."
  
  if ! check_command "clang-format" "C code"; then
    print_warning "Skipping C code formatting check (clang-format not installed)"
    print_warning "Alternatively, use 'qmk cformat' if QMK CLI is set up"
    return 0
  fi
  
  local keymap_dir="keymaps/keychron/v6_max/ansi_encoder/keymaps/dvorak_qwerty"
  
  if [[ ! -f "${keymap_dir}/keymap.c" ]]; then
    print_warning "Keymap file not found: ${keymap_dir}/keymap.c"
    return 0
  fi
  
  # Check if file would be modified by clang-format
  if ! clang-format --dry-run --Werror "${keymap_dir}/keymap.c" 2>/dev/null; then
    print_error "C code formatting check failed"
    print_warning "Run 'clang-format -i ${keymap_dir}/keymap.c' to fix"
    print_warning "Or use 'qmk cformat' if QMK CLI is available"
    EXIT_CODE=1
    return 1
  fi
  
  print_success "C code formatting check passed"
  return 0
}

run_all_lints() {
  print_header "Running all linters..."
  
  lint_python || true
  lint_shell || true
  lint_c || true
  
  if [[ $EXIT_CODE -eq 0 ]]; then
    echo ""
    print_success "All linting checks passed"
  else
    echo ""
    print_error "Some linting checks failed"
  fi
}

# Parse arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --python)
      LINT_TYPE="python"
      shift
      ;;
    --shell)
      LINT_TYPE="shell"
      shift
      ;;
    --c)
      LINT_TYPE="c"
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

# Execute requested linting
case "${LINT_TYPE}" in
  python)
    lint_python
    ;;
  shell)
    lint_shell
    ;;
  c)
    lint_c
    ;;
  all)
    run_all_lints
    ;;
esac

exit $EXIT_CODE
