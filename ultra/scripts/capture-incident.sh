#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage: capture-incident.sh [OPTIONS] [ULTRA_DIR]

Immediately freezes and dumps the V6 Ultra diagnostic RAM trace.
Run this before clearing the keyboard fault, rebooting or power-cycling.

ULTRA_DIR is detected from this script, the current directory, or
~/dwerty/ultra for the invoking user. Captures go to /mnt/shared when
available, or the current directory. Set DWERTY_CAPTURE_DIR to override.

A candidate interface is used only once it answers a diagnostic command, so a
receiver whose keyboard link is down is rejected rather than silently timing
out. Set DWERTY_SETTLE_SECONDS to change how long a freshly attached device is
given to answer.

After validating the saved trace, the default is to clear and re-arm the
diagnostic ring, then detach the wired keyboard from WSL so Windows can use it.
Use --keep-frozen to preserve the in-device trace, or --keep-attached to leave
the USB device attached to WSL.

Options:
  --hardware-id VID:PID  Select a specific usbipd device.
  --keep-frozen          Preserve the in-device frozen trace after saving.
  --keep-attached        Leave the selected USB device attached to WSL.
EOF
}

KEEP_FROZEN=0
KEEP_ATTACHED=0
HARDWARE_ID="${DWERTY_HARDWARE_ID:-}"
ULTRA_ARG=""
while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --hardware-id)
      shift
      if [[ "$#" == "0" ]]; then
        echo "--hardware-id requires VID:PID." >&2
        exit 2
      fi
      HARDWARE_ID="$1"
      ;;
    --hardware-id=*) HARDWARE_ID="${1#*=}" ;;
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
CMD_EXE="${DWERTY_CMD_EXE:-$(command -v cmd.exe 2>/dev/null || true)}"
if [[ -z "${USBIPD}" && -f "/mnt/c/Program Files/usbipd-win/usbipd.exe" ]]; then
  USBIPD="/mnt/c/Program Files/usbipd-win/usbipd.exe"
fi
if [[ -z "${CMD_EXE}" && -f "/mnt/c/Windows/System32/cmd.exe" ]]; then
  CMD_EXE="/mnt/c/Windows/System32/cmd.exe"
fi

run_usbipd() {
  if [[ -n "${USBIPD}" ]] && "${USBIPD}" "$@"; then
    return 0
  fi
  if [[ -n "${CMD_EXE}" ]]; then
    "${CMD_EXE}" /d /s /c "usbipd $*"
    return $?
  fi
  return 127
}

normalise_hardware_id() {
  local hardware_id="${1,,}"
  if [[ ! "${hardware_id}" =~ ^[0-9a-f]{4}:[0-9a-f]{4}$ ]]; then
    echo "Invalid hardware ID '${1}'; expected VID:PID such as 3434:d028." >&2
    return 2
  fi
  printf '%s\n' "${hardware_id}"
}

diagnostic_list() {
  local hardware_id="$1"
  local vid="${hardware_id%:*}"
  local pid="${hardware_id#*:}"
  "${DIAGNOSTICS}" --vid "0x${vid}" --pid "0x${pid}" list
}

diagnostic_probe() {
  local hardware_id="$1"
  local vid="${hardware_id%:*}"
  local pid="${hardware_id#*:}"
  "${DIAGNOSTICS}" --vid "0x${vid}" --pid "0x${pid}" info
}

# An enumerated interface only proves that the receiver is present. A receiver
# whose keyboard link is down still exposes the descriptor while answering
# nothing, so a candidate is accepted only once it replies.
diagnostic_ready() {
  local hardware_id="$1"
  local settle="$2"
  local deadline=$((SECONDS + settle))
  local candidate_json=""
  while true; do
    candidate_json="$(diagnostic_list "${hardware_id}" 2>/dev/null || true)"
    if grep -qE '"usage_page"[[:space:]]*:[[:space:]]*"ff60"' <<<"${candidate_json}" &&
       diagnostic_probe "${hardware_id}" >/dev/null 2>&1; then
      printf '%s\n' "${candidate_json}"
      return 0
    fi
    if [[ "${SECONDS}" -ge "${deadline}" ]]; then
      return 1
    fi
    sleep 1
  done
}

usbipd_busid() {
  local usbipd_list="$1"
  local hardware_id="$2"
  awk -v hardware_id="${hardware_id}" '{
    for (field = 1; field <= NF; field++) {
      if (tolower($field) == hardware_id) {
        print $1
        exit
      }
    }
  }' <<<"${usbipd_list}"
}

if [[ -n "${HARDWARE_ID}" ]]; then
  HARDWARE_ID="$(normalise_hardware_id "${HARDWARE_ID}")"
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

if [[ "${EUID}" -ne 0 && "${DWERTY_CAPTURE_TEST_MODE:-0}" != "1" ]]; then
  sudo_env=()
  sudo_args=()
  if [[ -n "${DWERTY_CAPTURE_DIR:-}" ]]; then
    sudo_env+=("DWERTY_CAPTURE_DIR=${DWERTY_CAPTURE_DIR}")
  fi
  if [[ -n "${DWERTY_SETTLE_SECONDS:-}" ]]; then
    sudo_env+=("DWERTY_SETTLE_SECONDS=${DWERTY_SETTLE_SECONDS}")
  fi
  if [[ -n "${USBIPD}" ]]; then
    sudo_env+=("DWERTY_USBIPD=${USBIPD}")
  fi
  if [[ -n "${CMD_EXE}" ]]; then
    sudo_env+=("DWERTY_CMD_EXE=${CMD_EXE}")
  fi
  if [[ -n "${HARDWARE_ID}" ]]; then
    sudo_args+=(--hardware-id "${HARDWARE_ID}")
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

ATTACHED_BUSID=""
TEMPORARY=""
SETTLE_SECONDS="${DWERTY_SETTLE_SECONDS:-20}"

# A failed capture must not strand the keyboard in WSL, where Windows cannot
# use it and the next attempt has to start by reattaching it.
cleanup() {
  local status=$?
  if [[ -n "${TEMPORARY}" ]]; then
    rm -f "${TEMPORARY}"
  fi
  if [[ "${status}" -ne 0 && "${KEEP_ATTACHED}" != "1" && -n "${ATTACHED_BUSID}" ]]; then
    if run_usbipd detach --busid "${ATTACHED_BUSID}" >/dev/null 2>&1; then
      echo "Detached ${ATTACHED_BUSID} from WSL after the failed capture." >&2
    fi
  fi
  return "${status}"
}
trap cleanup EXIT

CANDIDATE_IDS=()
if [[ -n "${HARDWARE_ID}" ]]; then
  CANDIDATE_IDS=("${HARDWARE_ID}")
else
  # Prefer the receiver so a wireless incident can be retrieved without
  # changing keyboard transport. Fall back to the direct wired keyboard.
  CANDIDATE_IDS=("3434:d028" "3434:0c60")
fi

SELECTED_HARDWARE_ID=""
device_json=""
for candidate in "${CANDIDATE_IDS[@]}"; do
  if candidate_json="$(diagnostic_ready "${candidate}" 0)"; then
    SELECTED_HARDWARE_ID="${candidate}"
    device_json="${candidate_json}"
    break
  fi
done

if [[ -z "${SELECTED_HARDWARE_ID}" && ( -n "${USBIPD}" || -n "${CMD_EXE}" ) ]]; then
  initial_usbipd_list="$(run_usbipd list 2>/dev/null | tr -d '\r' || true)"
  for candidate in "${CANDIDATE_IDS[@]}"; do
    candidate_busid="$(usbipd_busid "${initial_usbipd_list}" "${candidate}")"
    if [[ ! "${candidate_busid}" =~ ^[0-9]+-[0-9]+$ ]]; then
      continue
    fi
    echo "Attaching ${candidate} (${candidate_busid}) to WSL for diagnostic capture..." >&2
    run_usbipd attach --wsl --busid "${candidate_busid}" >/dev/null 2>&1 || true
    ATTACHED_BUSID="${candidate_busid}"
    if candidate_json="$(diagnostic_ready "${candidate}" "${SETTLE_SECONDS}")"; then
      SELECTED_HARDWARE_ID="${candidate}"
      device_json="${candidate_json}"
      break
    fi
    run_usbipd detach --busid "${candidate_busid}" >/dev/null 2>&1 || true
    ATTACHED_BUSID=""
  done
fi

if [[ -z "${SELECTED_HARDWARE_ID}" ]]; then
  echo "No supported diagnostic HID interface answered." >&2
  echo "Known defaults: 3434:d028 (receiver), 3434:0c60 (wired)." >&2
  echo "A receiver enumerates even when its keyboard link is down; press a key" >&2
  echo "to wake the link, or capture on the transport the keyboard is using." >&2
  echo "Override with: --hardware-id VID:PID" >&2
  exit 1
fi

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
capture="${OUTPUT_DIR}/dwerty-incident-${timestamp}.jsonl"
metadata="${OUTPUT_DIR}/dwerty-incident-${timestamp}.txt"
TEMPORARY="$(mktemp "${OUTPUT_DIR}/.dwerty-incident.XXXXXX")"

echo "Freezing diagnostic state and writing ${capture}..." >&2
vid="${SELECTED_HARDWARE_ID%:*}"
pid="${SELECTED_HARDWARE_ID#*:}"
DIAGNOSTIC_ARGS=(--vid "0x${vid}" --pid "0x${pid}")
"${DIAGNOSTICS}" "${DIAGNOSTIC_ARGS[@]}" dump --output "${TEMPORARY}"
mv "${TEMPORARY}" "${capture}"
TEMPORARY=""

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
  echo "hardware_id=${SELECTED_HARDWARE_ID}"
  echo "device=${device_json}"
  echo "header=$(head -n 1 "${capture}")"
  echo "schema_command=${DIAGNOSTICS} schema"
  echo "analyse_command=${DIAGNOSTICS} analyse ${capture}"
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

analysis="$("${DIAGNOSTICS}" analyse "${capture}" 2>/dev/null || true)"
if [[ -n "${analysis}" ]]; then
  {
    echo "analysis_begin"
    printf '%s\n' "${analysis}"
    echo "analysis_end"
  } >>"${metadata}"
  echo "Analysis:"
  printf '%s\n' "${analysis}"
  echo
fi

if [[ "${KEEP_FROZEN}" == "1" ]]; then
  echo "Diagnostic ring left frozen (--keep-frozen)." | tee -a "${metadata}"
else
  rearm_json="$("${DIAGNOSTICS}" "${DIAGNOSTIC_ARGS[@]}" arm)"
  echo "rearm=${rearm_json}" >>"${metadata}"
  echo "Diagnostic ring cleared and re-armed."
fi

if [[ "${KEEP_ATTACHED}" == "1" ]]; then
  echo "Wired keyboard left attached to WSL (--keep-attached)." | tee -a "${metadata}"
elif [[ -n "${USBIPD}" || -n "${CMD_EXE}" ]]; then
  usbipd_list="$(run_usbipd list 2>/dev/null | tr -d '\r' || true)"
  {
    echo "usbipd_list_begin"
    printf '%s\n' "${usbipd_list}"
    echo "usbipd_list_end"
  } >>"${metadata}"
  busid="$(usbipd_busid "${usbipd_list}" "${SELECTED_HARDWARE_ID}")"
  if [[ "${busid}" =~ ^[0-9]+-[0-9]+$ ]] &&
     run_usbipd detach --busid "${busid}" >/dev/null 2>&1; then
    echo "usbipd_detached_busid=${busid}" >>"${metadata}"
    echo "Detached ${SELECTED_HARDWARE_ID} (${busid}) from WSL; Windows can use it again."
  else
    echo "usbipd_detach=failed busid=${busid:-not-found}" >>"${metadata}"
    echo "Could not detach the keyboard; it remains attached to WSL." >&2
    echo "Run: usbipd.exe detach --busid <BUSID>" >&2
  fi
fi

chmod 0600 "${capture}" "${metadata}"
if [[ -n "${SUDO_UID:-}" ]]; then
  chown "${ORIGINAL_UID}:${ORIGINAL_GID}" "${capture}" "${metadata}"
fi
