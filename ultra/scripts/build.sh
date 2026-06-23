#!/usr/bin/env bash
# Build the Keychron V6 Ultra 8K ZMK firmware with our DWERTY keymap.
#
# Uses Keychron's ZMK fork (rtl8762g) in a Podman container. The compiled
# image (zmk.elf/hex/bin) is the deliverable; the final Realtek OTA
# header-prepend step is x86-only and is handled separately (see scripts and
# the README "Flashing" section), so a non-zero exit from that last step is
# tolerated as long as the firmware image was produced.
#
# Usage: ./scripts/build.sh [--clean]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ULTRA_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

WS="${ULTRA_DIR}/.cache/fork"          # west workspace (zmk at $WS/zmk)
ZMK="${WS}/zmk"
IMAGE="docker.io/zmkfirmware/zmk-build-arm:3.5"
ZMK_REPO="https://github.com/Keychron/zmk.git"
ZMK_BRANCH="rtl8762g"
BOARD="keychron"
SHIELD="keychron_v6_ultra_ansi"
SHIELD_DIR_REL="app/boards/shields/${SHIELD}"

USERNS=(--userns=keep-id)

if [[ "${1:-}" == "--clean" ]]; then
  echo "Removing ${WS} ..."
  rm -rf "${WS}"
fi

mkdir -p "${WS}"

run() {  # run a command inside the build container, mounting the workspace
  podman run --rm "${USERNS[@]}" \
    -v "${WS}:/ws:Z" -v "${ULTRA_DIR}:/ultra:Z" -w /ws \
    "${IMAGE}" bash -lc "$1"
}

# 1. Initialise the west workspace (clone fork + pull Zephyr) once.
if [[ ! -d "${ZMK}/.git" ]]; then
  echo "==> Cloning ${ZMK_REPO} (${ZMK_BRANCH}) and running west update (slow, one-time)"
  git clone --depth 1 -b "${ZMK_BRANCH}" "${ZMK_REPO}" "${ZMK}"
  run 'git config --global --add safe.directory "*"
       cd /ws/zmk && west init -l app && west update && west zephyr-export'
fi

# 2. Apply our keymap + conf overrides onto a clean stock shield.
echo "==> Applying DWERTY keymap and conf overrides"
run "git config --global --add safe.directory '*'
     cd /ws/zmk && git checkout -- ${SHIELD_DIR_REL} 2>/dev/null || true
     cp /ultra/config/${SHIELD}.keymap ${SHIELD_DIR_REL}/${SHIELD}.keymap
     cat /ultra/config/${SHIELD}.conf >> ${SHIELD_DIR_REL}/${SHIELD}.conf"

# 3. Build. Tolerate the x86-only RTK header post-build step failing.
echo "==> Building ${SHIELD} for board ${BOARD}"
run "git config --global --add safe.directory '*'
     cd /ws/zmk && west build -p -s app -b ${BOARD} -- -DSHIELD=${SHIELD}" || true

# 4. Collect artefacts.
OUT="${ULTRA_DIR}/build"
mkdir -p "${OUT}"
ok=0
for ext in elf hex bin; do
  f="${ZMK}/build/zephyr/zmk.${ext}"
  if [[ -f "${f}" ]]; then cp -f "${f}" "${OUT}/"; ok=1; fi
done

if [[ "${ok}" == "1" ]]; then
  echo "==> SUCCESS: firmware image(s) in ultra/build/"
  ls -la "${OUT}"
  echo "    (Realtek OTA header packaging for flashing: see scripts/package.sh / README)"
else
  echo "==> FAILED: no firmware image produced. See build log above." >&2
  exit 1
fi
