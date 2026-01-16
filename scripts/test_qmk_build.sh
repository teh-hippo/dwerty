#!/usr/bin/env bash
# Backward compatibility wrapper for test.sh --build
# This script is deprecated. Use: ./scripts/test.sh --build

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${SCRIPT_DIR}/test.sh" --build
