#!/usr/bin/env bash
# Backward compatibility wrapper for test.sh --integration
# This script is deprecated. Use: ./scripts/test.sh --integration

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${SCRIPT_DIR}/test.sh" --integration
