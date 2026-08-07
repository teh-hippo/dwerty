#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage: capture-incident.sh [--keep-frozen] [--keep-attached] [ULTRA_DIR]

Immediately freezes and dumps the V6 Ultra diagnostic RAM trace.
Run this before clearing the keyboard fault, rebooting or power-cycling.

ULTRA_DIR is detected from this script, the current directory, or
~/dwerty/ultra for the invoking user. Captures go to /mnt/shared when
available, or the current directory. Set DWERTY_CAPTURE_DIR to override.

After validating the saved trace, the default is to clear and re-arm the
diagnostic ring, then detach the wired keyboard from WSL so Windows can use it.
Use --keep-frozen to preserve the in-device trace, or --keep-attached to leave
the USB device attached to WSL.
EOF
}

KEEP_FROZEN=0
KEEP_ATTACHED=0
ULTRA_ARG=""
while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --keep-frozen) KEEP_FROZEN=1 ;;
    --keep-attached) KEEP_ATTACHED=1 ;;
    --help|-h)
      usage
      exit 0
      ;;
    --)
      shift
      if [[ "$#" -gt 1 ]]; then
        usage >&2
        exit 2
      fi
      ULTRA_ARG="${1:-}"
      break
      ;;
    -*)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
    *)
      if [[ -n "${ULTRA_ARG}" ]]; then
        usage >&2
        exit 2
      fi
      ULTRA_ARG="$1"
      ;;
  esac
  shift
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ORIGINAL_USER="${SUDO_USER:-${USER:-}}"
ORIGINAL_UID="${SUDO_UID:-$(id -u)}"
ORIGINAL_GID="${SUDO_GID:-$(id -g)}"
USBIPD="${DWERTY_USBIPD:-$(command -v usbipd.exe 2>/dev/null || true)}"
if [[ -z "${USBIPD}" && -x "/mnt/c/Program Files/usbipd-win/usbipd.exe" ]]; then
  USBIPD="/mnt/c/Program Files/usbipd-win/usbipd.exe"
fi

if [[ -n "${ULTRA_ARG}" ]]; then
  ULTRA_DIR="$(realpath "${ULTRA_ARG}")"
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
  sudo_args=()
  if [[ -n "${DWERTY_CAPTURE_DIR:-}" ]]; then
    sudo_env+=("DWERTY_CAPTURE_DIR=${DWERTY_CAPTURE_DIR}")
  fi
  if [[ -n "${USBIPD}" ]]; then
    sudo_env+=("DWERTY_USBIPD=${USBIPD}")
  fi
  if [[ "${KEEP_FROZEN}" == "1" ]]; then
    sudo_args+=(--keep-frozen)
  fi
  if [[ "${KEEP_ATTACHED}" == "1" ]]; then
    sudo_args+=(--keep-attached)
  fi
  exec sudo env "${sudo_env[@]}" "$0" "${sudo_args[@]}" "${ULTRA_DIR}"
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

validation="$(python3 - "${capture}" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
lines = path.read_text(encoding="utf-8").splitlines()
if not lines:
    raise SystemExit("capture is empty")
objects = [json.loads(line) for line in lines]
header = objects[0]
if header.get("kind") != "info" or not header.get("frozen"):
    raise SystemExit("capture does not contain a frozen diagnostic header")
expected = header.get("count")
actual = sum(item.get("kind") == "record" for item in objects[1:])
if not isinstance(expected, int) or actual != expected:
    raise SystemExit(f"capture record count mismatch: header={expected}, file={actual}")
print(f"validated_records={actual}")
PY
)"

{
  echo "capture_utc=${timestamp}"
  echo "host=$(hostname)"
  echo "ultra_dir=${ULTRA_DIR}"
  echo "repository_commit=$(git -C "${ULTRA_DIR}" rev-parse HEAD 2>/dev/null || echo unknown)"
  echo "device=${device_json}"
  echo "header=$(head -n 1 "${capture}")"
  echo "${validation}"
} >"${metadata}"

echo
echo "Captured:"
echo "  ${capture}"
echo "  ${metadata}"
echo
echo "Header:"
head -n 1 "${capture}"
echo

if [[ "${KEEP_FROZEN}" == "1" ]]; then
  echo "Diagnostic ring left frozen (--keep-frozen)." | tee -a "${metadata}"
else
  rearm_json="$("${DIAGNOSTICS}" arm)"
  echo "rearm=${rearm_json}" >>"${metadata}"
  echo "Diagnostic ring cleared and re-armed."
fi

if [[ "${KEEP_ATTACHED}" == "1" ]]; then
  echo "Wired keyboard left attached to WSL (--keep-attached)." | tee -a "${metadata}"
elif [[ -n "${USBIPD}" && -x "${USBIPD}" ]]; then
  busid="$("${USBIPD}" list 2>/dev/null | tr -d '\r' |
    awk 'tolower($2) == "3434:0c60" { print $1; exit }')"
  if [[ -n "${busid}" ]]; then
    "${USBIPD}" detach --busid "${busid}" >/dev/null
    echo "usbipd_detached_busid=${busid}" >>"${metadata}"
    echo "Detached ${busid} from WSL; Windows can use the wired keyboard again."
  else
    echo "usbipd_busid=not-found" >>"${metadata}"
    echo "Could not identify the usbipd bus ID; the keyboard remains attached to WSL." >&2
  fi
fi

chmod 0600 "${capture}" "${metadata}"
if [[ -n "${SUDO_UID:-}" ]]; then
  chown "${ORIGINAL_UID}:${ORIGINAL_GID}" "${capture}" "${metadata}"
fi
