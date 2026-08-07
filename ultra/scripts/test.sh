#!/usr/bin/env bash
# Run the DWERTY behaviour tests with no hardware. The host simulation is pinned
# to the Keychron fork's upstream merge base, where behavior_mod_morph.c and the
# keymap release-routing function are byte-identical to the pinned fork.
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
ZMK_SHA="931a36ff4ad0b30c8165024bbfc0286d05b74b53"
KEYCHRON_REPO="https://github.com/Keychron/zmk.git"
KEYCHRON_SHA="101a23c678495ff2a08a86d59c7a7869350d39a6"
TEST_PATCHES=(
  "${ULTRA_DIR}/patches/0003-preserve-press-layer-on-release.patch"
  "${ULTRA_DIR}/tests/patches/default-layer-test-hook.patch"
)

# Container engine: podman locally (default), or set DWERTY_CONTAINER_ENGINE=docker
# (e.g. in CI on x86_64). Only podman gets --userns=keep-id and SELinux :Z labels.
ENGINE="${DWERTY_CONTAINER_ENGINE:-}"
if [[ -z "${ENGINE}" ]]; then
  if command -v podman >/dev/null 2>&1; then ENGINE=podman; else ENGINE=docker; fi
fi
RUN_FLAGS=(--rm)
MOUNT=""
if [[ "${ENGINE}" == "podman" ]]; then
  RUN_FLAGS+=(--userns=keep-id)
  MOUNT=":Z"
fi

if [[ "${1:-}" == "--clean" ]]; then rm -rf "${WS}"; shift; fi
CASE="${1:-}"

# Host-side parity: the Ultra DQ pairs must match the Max keymap exactly.
echo "==> Checking Dvorak->Qwerty parity with max/"
bash -n \
  "${ULTRA_DIR}/scripts/build.sh" \
  "${ULTRA_DIR}/scripts/capture-incident.sh" \
  "${ULTRA_DIR}/scripts/package.sh" \
  "${ULTRA_DIR}/scripts/test.sh" \
  "${ULTRA_DIR}/tests/test_capture_incident.sh"
bash "${ULTRA_DIR}/tests/test_capture_incident.sh"
python3 "${ULTRA_DIR}/tests/parity_dq.py"
python3 -m unittest discover -s "${ULTRA_DIR}/tests" -p "test_*.py"

mkdir -p "${WS}"

run() {
  "${ENGINE}" run "${RUN_FLAGS[@]}" \
    -v "${WS}:/ws${MOUNT}" -v "${ULTRA_DIR}:/ultra${MOUNT}" -w /ws \
    "${IMAGE}" bash -lc "$1"
}

# 1. Prepare the pinned upstream checkout. Remove our test patches before a
# revision change so a persistent local cache can move cleanly to a new pin.
PREVIOUS_SHA=""
if [[ ! -d "${ZMK}/.git" ]]; then
  echo "==> Cloning upstream ${ZMK_REPO} @ ${ZMK_SHA:0:7}"
  git clone --filter=blob:none --no-checkout "${ZMK_REPO}" "${ZMK}"
else
  PREVIOUS_SHA="$(git -C "${ZMK}" rev-parse HEAD)"
  for p in "${TEST_PATCHES[@]}"; do
    if git -C "${ZMK}" apply --reverse --check "${p}" 2>/dev/null; then
      git -C "${ZMK}" apply --reverse "${p}"
    fi
  done
fi

git -C "${ZMK}" fetch --depth 1 origin "${ZMK_SHA}"
git -C "${ZMK}" checkout -q "${ZMK_SHA}"

if [[ ! -d "${ZMK}/.west" ]]; then
  echo "==> Initialising west workspace (slow, one-time)"
  run 'git config --global --add safe.directory "*"
       cd /ws/zmk && west init -l app && west update && west zephyr-export'
elif [[ -n "${PREVIOUS_SHA}" && "${PREVIOUS_SHA}" != "${ZMK_SHA}" ]]; then
  echo "==> Updating west modules for new upstream pin"
  run 'git config --global --add safe.directory "*"
       cd /ws/zmk && west update && west zephyr-export'
fi

# 2. Pin both source revisions and verify the exact code paths our tests model.
if ! git -C "${ZMK}" remote get-url keychron >/dev/null 2>&1; then
  git -C "${ZMK}" remote add keychron "${KEYCHRON_REPO}"
fi
git -C "${ZMK}" fetch --depth 1 keychron "${KEYCHRON_SHA}"

echo "==> Checking pinned fork source invariants"
python3 "${ULTRA_DIR}/tests/source_invariants.py" \
  --zmk "${ZMK}" \
  --base "${ZMK_SHA}" \
  --fork "${KEYCHRON_SHA}" \
  --ultra "${ULTRA_DIR}"

# 3. Apply the production release fix and test-only default-layer mutators.
for p in "${TEST_PATCHES[@]}"; do
  if git -C "${ZMK}" apply --reverse --check "${p}" 2>/dev/null; then
    echo "    already applied: $(basename "${p}")"
  else
    git -C "${ZMK}" apply "${p}" && echo "    applied: $(basename "${p}")"
  fi
done

# 4. Sync our tests into the workspace and run them. This historical ZMK
# revision calls its host board native_posix_64; keep the committed native_sim
# names and create the expected filename only inside the generated workspace.
echo "==> Running pinned host-simulation behaviour tests"
run "git config --global --add safe.directory '*'
     cd /ws/zmk
     rm -rf app/tests/ultra && mkdir -p app/tests/ultra
     cp -r /ultra/tests/* app/tests/ultra/
     find app/tests/ultra -name native_sim.keymap -exec sh -c \
       'cp \"\$1\" \"\${1%/*}/native_posix_64.keymap\"' _ {} \;
     cd app
     find tests/ultra -name native_posix_64.keymap -exec dirname {} \; |
       while read -r testcase; do mkdir -p \"build/\${testcase}\"; done
     ./run-test.sh tests/ultra/${CASE}"
