#!/usr/bin/env bash
# Backward compatibility wrapper for flash.sh --easy
# This script is deprecated. Use: ./scripts/flash.sh --easy

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${SCRIPT_DIR}/flash.sh" --easy
