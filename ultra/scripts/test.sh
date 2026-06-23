#!/usr/bin/env bash
# Run the DWERTY behaviour tests (ZMK native_sim snapshot tests) with no
# hardware. These run on UPSTREAM zmkfirmware/zmk: the &mod_morph + keep-mods
# behaviour is identical to Keychron's fork, and the fork itself cannot
# host-test (its core headers pull in the Realtek HAL).
#
# Usage: ./scripts/test.sh [--clean] [testcase]
#   testcase: a path under ultra/tests (default: all of ultra/tests)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ULTRA_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

WS="${ULTRA_DIR}/.cache/upstream"      # west workspace (zmk at $WS/zmk)
ZMK="${WS}/zmk"
IMAGE="docker.io/zmkfirmware/zmk-build-arm:4.1"
ZMK_REPO="https://github.com/zmkfirmware/zmk.git"

USERNS=(--userns=keep-id)

if [[ "${1:-}" == "--clean" ]]; then rm -rf "${WS}"; shift; fi
CASE="${1:-}"

mkdir -p "${WS}"

run() {
  podman run --rm "${USERNS[@]}" \
    -v "${WS}:/ws:Z" -v "${ULTRA_DIR}:/ultra:Z" -w /ws \
    "${IMAGE}" bash -lc "$1"
}

# 1. Initialise the upstream west workspace once.
if [[ ! -d "${ZMK}/.git" ]]; then
  echo "==> Cloning upstream ${ZMK_REPO} and running west update (slow, one-time)"
  git clone --depth 1 "${ZMK_REPO}" "${ZMK}"
  run 'git config --global --add safe.directory "*"
       cd /ws/zmk && west init -l app && west update && west zephyr-export'
fi

# 2. Sync our tests into the workspace and run them.
echo "==> Running native_sim behaviour tests"
run "git config --global --add safe.directory '*'
     cd /ws/zmk
     rm -rf app/tests/ultra && mkdir -p app/tests/ultra
     cp -r /ultra/tests/* app/tests/ultra/
     cd app && ./run-test.sh tests/ultra/${CASE}"
