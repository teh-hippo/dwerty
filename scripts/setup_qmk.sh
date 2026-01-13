#!/usr/bin/env bash
set -euo pipefail

QMK_DIR="${QMK_DIR:-$HOME/qmk_firmware}"
QMK_REPO_DEFAULT="https://github.com/Keychron/qmk_firmware.git"
QMK_BRANCH_DEFAULT="wireless_playground"
QMK_REPO_UPSTREAM="https://github.com/qmk/qmk_firmware.git"
QMK_BRANCH_UPSTREAM="master"

REPO="${QMK_REPO_DEFAULT}"
BRANCH="${QMK_BRANCH_DEFAULT}"

if [[ "${1:-}" == "--upstream" ]]; then
  REPO="${QMK_REPO_UPSTREAM}"
  BRANCH="${QMK_BRANCH_UPSTREAM}"
fi

if [[ -e "${QMK_DIR}" ]]; then
  echo "QMK_DIR already exists: ${QMK_DIR}" >&2
  echo "Set QMK_DIR to a new location or remove the existing directory." >&2
  exit 1
fi

git clone "${REPO}" "${QMK_DIR}"
(cd "${QMK_DIR}" && git checkout "${BRANCH}")

if [[ ! -f "${QMK_DIR}/keyboards/keychron/v6_max/info.json" ]]; then
  echo "V6 Max support not found in ${REPO} (${BRANCH})." >&2
  echo "Use the Keychron fork or wait for upstream support." >&2
  exit 1
fi

echo "QMK cloned to ${QMK_DIR} (${REPO} @ ${BRANCH})"
