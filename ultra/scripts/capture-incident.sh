#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage: capture-incident.sh [ULTRA_DIR]

Immediately freezes and dumps the V6 Ultra diagnostic RAM trace.
Run this before clearing the keyboard fault, rebooting or power-cycling.

ULTRA_DIR is detected from this script, the current directory, or
~/dwerty/ultra for the invoking user. Captures go to /mnt/shared when
available, or the current directory. Set DWERTY_CAPTURE_DIR to override.
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi
if [[ "$#" -gt 1 ]]; then
  usage >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ORIGINAL_USER="${SUDO_USER:-${USER:-}}"
ORIGINAL_UID="${SUDO_UID:-$(id -u)}"
ORIGINAL_GID="${SUDO_GID:-$(id -g)}"
USBIPD="${DWERTY_USBIPD:-$(command -v usbipd.exe 2>/dev/null || true)}"
if [[ -z "${USBIPD}" && -x "/mnt/c/Program Files/usbipd-win/usbipd.exe" ]]; then
  USBIPD="/mnt/c/Program Files/usbipd-win/usbipd.exe"
fi

if [[ -n "${1:-}" ]]; then
  ULTRA_DIR="$(realpath "$1")"
elif [[ -x "${SCRIPT_DIR}/diagnostics.py" ]]; then
  ULTRA_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
elif [[ -x "${PWD}/scripts/diagnostics.py" ]]; then
  ULTRA_DIR="${PWD}"
elif [[ -n "${ORIGINAL_USER}" &&
        -x "/home/${ORIGINAL_USER}/dwerty/ultra/scripts/diagnostics.py" ]]; then
  ULTRA_DIR="/home/${ORIGINAL_USER}/dwerty/ultra"
else
  echo "Cannot locate dwerty/ultra; pass its path as the first argument." >&2
  exit 2
fi

if [[ "${EUID}" -ne 0 ]]; then
  sudo_env=()
  if [[ -n "${DWERTY_CAPTURE_DIR:-}" ]]; then
    sudo_env+=("DWERTY_CAPTURE_DIR=${DWERTY_CAPTURE_DIR}")
  fi
  if [[ -n "${USBIPD}" ]]; then
    sudo_env+=("DWERTY_USBIPD=${USBIPD}")
  fi
  exec sudo env "${sudo_env[@]}" "$0" "${ULTRA_DIR}"
fi

DIAGNOSTICS="${ULTRA_DIR}/scripts/diagnostics.py"
if [[ ! -x "${DIAGNOSTICS}" ]]; then
  echo "Missing executable ${DIAGNOSTICS}" >&2
  exit 2
fi

if [[ -n "${DWERTY_CAPTURE_DIR:-}" ]]; then
  OUTPUT_DIR="${DWERTY_CAPTURE_DIR}"
elif [[ -d /mnt/shared ]]; then
  OUTPUT_DIR="/mnt/shared"
else
  OUTPUT_DIR="${PWD}"
fi
mkdir -p "${OUTPUT_DIR}"

device_json="$("${DIAGNOSTICS}" list)"
if ! grep -q '"usage_page": "ff60"' <<<"${device_json}"; then
  if [[ -n "${USBIPD}" && -x "${USBIPD}" ]]; then
    echo "Diagnostic HID is not attached; asking usbipd to attach it to WSL..." >&2
    "${USBIPD}" attach --wsl --hardware-id 3434:0c60 >/dev/null 2>&1 || true
    sleep 2
    device_json="$("${DIAGNOSTICS}" list)"
  fi
fi
if ! grep -q '"usage_page": "ff60"' <<<"${device_json}"; then
  echo "No V6 Ultra diagnostic HID interface found." >&2
  echo "Attach it with: usbipd.exe attach --wsl --hardware-id 3434:0c60" >&2
  exit 1
fi

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
capture="${OUTPUT_DIR}/dwerty-incident-${timestamp}.jsonl"
metadata="${OUTPUT_DIR}/dwerty-incident-${timestamp}.txt"
temporary="$(mktemp "${OUTPUT_DIR}/.dwerty-incident.XXXXXX")"
trap 'rm -f "${temporary}"' EXIT

echo "Freezing diagnostic state and writing ${capture}..." >&2
"${DIAGNOSTICS}" dump --output "${temporary}"
mv "${temporary}" "${capture}"
trap - EXIT

{
  echo "capture_utc=${timestamp}"
  echo "host=$(hostname)"
  echo "ultra_dir=${ULTRA_DIR}"
  echo "repository_commit=$(git -C "${ULTRA_DIR}" rev-parse HEAD 2>/dev/null || echo unknown)"
  echo "device=${device_json}"
  echo "header=$(head -n 1 "${capture}")"
} >"${metadata}"

chmod 0600 "${capture}" "${metadata}"
if [[ -n "${SUDO_UID:-}" ]]; then
  chown "${ORIGINAL_UID}:${ORIGINAL_GID}" "${capture}" "${metadata}"
fi

echo
echo "Captured:"
echo "  ${capture}"
echo "  ${metadata}"
echo
echo "Header:"
head -n 1 "${capture}"
echo
echo "Do not run arm until these files have been copied and reviewed."
