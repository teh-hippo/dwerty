#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME="${IMAGE_NAME:-dwerty-qmk}"
CONTAINERFILE="${CONTAINERFILE:-Containerfile}"

podman build -t "${IMAGE_NAME}" -f "${CONTAINERFILE}" .
