#!/usr/bin/env bash
set -euo pipefail

QMK_DIR="${QMK_DIR:-$HOME/qmk_firmware}"
REMOTE="${QMK_REMOTE:-origin}"
BRANCH="${QMK_BRANCH:-}"

if [[ ! -d "${QMK_DIR}/.git" ]]; then
  echo "QMK_DIR is not a git repo: ${QMK_DIR}" >&2
  exit 1
fi

if [[ -z "${BRANCH}" ]]; then
  current_branch=$(git -C "${QMK_DIR}" rev-parse --abbrev-ref HEAD)
  if [[ "${current_branch}" != "HEAD" ]]; then
    BRANCH="${current_branch}"
  else
    default_ref=$(git -C "${QMK_DIR}" symbolic-ref --quiet --short "refs/remotes/${REMOTE}/HEAD" || true)
    if [[ -n "${default_ref}" ]]; then
      BRANCH="${default_ref#"${REMOTE}"/}"
    else
      echo "Cannot determine branch; set QMK_BRANCH explicitly." >&2
      exit 1
    fi
  fi
fi

if [[ -n "$(git -C "${QMK_DIR}" status --porcelain)" ]]; then
  echo "QMK repo has uncommitted changes. Commit or stash before updating." >&2
  exit 1
fi

git -C "${QMK_DIR}" fetch "${REMOTE}" --tags
git -C "${QMK_DIR}" checkout "${BRANCH}"
# Keep the QMK repo linear and clean; fail if fast-forward is not possible.
git -C "${QMK_DIR}" pull --ff-only "${REMOTE}" "${BRANCH}"

if [[ ! -f "${QMK_DIR}/keyboards/keychron/v6_max/info.json" ]]; then
  echo "V6 Max support not found after update; you may be on a branch without it." >&2
  exit 1
fi

echo "QMK updated: ${REMOTE}/${BRANCH}"
