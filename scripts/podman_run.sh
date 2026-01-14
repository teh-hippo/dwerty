#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME="${IMAGE_NAME:-dwerty-qmk}"
WORKDIR="${WORKDIR:-/workspace}"

podman run --rm -it \
  -v "${PWD}:${WORKDIR}:Z" \
  -w "${WORKDIR}" \
  "${IMAGE_NAME}" \
  bash
