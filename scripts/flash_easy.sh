#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"${SCRIPT_DIR}/install_keymap.sh"
"${SCRIPT_DIR}/build.sh"
"${SCRIPT_DIR}/flash.sh"
