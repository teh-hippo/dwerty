#!/usr/bin/env bash

set -euo pipefail

ULTRA_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COLLECTOR="${ULTRA_DIR}/scripts/capture-incident.sh"

make_fixture() {
  local root="$1"
  mkdir -p "${root}/ultra/scripts" "${root}/out"

  cat >"${root}/ultra/scripts/diagnostics.py" <<'EOF'
#!/usr/bin/env bash
pid=""
command=""
output=""
while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --pid) pid="$2"; shift ;;
    list|arm|dump|info) command="$1" ;;
    --output) output="$2"; shift ;;
  esac
  shift
done
attached=""
[[ "${pid}" == "0xd028" ]] && attached="${TMP_STATE}/receiver" && short=d028
[[ "${pid}" == "0x0c60" ]] && attached="${TMP_STATE}/wired" && short=0c60
case "${command}" in
  list)
    [[ -n "${attached}" && -f "${attached}" ]] &&
      echo "{\"usage_page\":\"ff60\",\"pid\":\"${short}\"}" || true
    ;;
  info)
    [[ -n "${attached}" && -f "${attached}" && ! -f "${TMP_STATE}/mute-${short}" ]] ||
      exit 1
    echo '{"kind":"info","count":1,"frozen":false}'
    ;;
  dump)
    [[ -f "${TMP_STATE}/dump-fails" ]] && exit 1
    printf '%s\n' \
      '{"kind":"info","frozen":true,"count":1}' \
      '{"kind":"record"}' >"${output}"
    ;;
  arm) echo '{"kind":"info","count":1}' ;;
esac
EOF
  chmod +x "${root}/ultra/scripts/diagnostics.py"

  cat >"${root}/usbipd.exe" <<'EOF'
#!/usr/bin/env bash
case "$1" in
  list)
    printf 'BUSID VID:PID DEVICE STATE\n'
    [[ -f "${TMP_STATE}/receiver" ]] && receiver=Attached || receiver=Shared
    [[ -f "${TMP_STATE}/wired" ]] && wired=Attached || wired=Shared
    printf '9-3 3434:d028 Receiver %s\n' "${receiver}"
    printf '11-1 3434:0c60 Keyboard %s\n' "${wired}"
    ;;
  attach)
    [[ "${4:-}" == "9-3" ]] && touch "${TMP_STATE}/receiver"
    [[ "${4:-}" == "11-1" ]] && touch "${TMP_STATE}/wired"
    ;;
  detach)
    echo "$*" >>"${TMP_STATE}/detach.log"
    [[ "${3:-}" == "9-3" ]] && rm -f "${TMP_STATE}/receiver"
    [[ "${3:-}" == "11-1" ]] && rm -f "${TMP_STATE}/wired"
    ;;
esac
exit 0
EOF
  chmod +x "${root}/usbipd.exe"
}

run_case() (
  local expected_id="$1"
  local expected_busid="$2"
  shift 2
  local root
  root="$(mktemp -d)"
  trap 'rm -rf "${root}"' EXIT
  make_fixture "${root}"
  for marker in ${PRESET_MARKERS:-}; do
    touch "${root}/${marker}"
  done

  TMP_STATE="${root}" \
    DWERTY_CAPTURE_DIR="${root}/out" \
    DWERTY_CAPTURE_TEST_MODE=1 \
    DWERTY_SETTLE_SECONDS=0 \
    DWERTY_USBIPD="${root}/usbipd.exe" \
    "${COLLECTOR}" "$@" "${root}/ultra" >"${root}/run.out"

  grep -q "^hardware_id=${expected_id}$" "${root}"/out/*.txt
  grep -q "detach --busid ${expected_busid}" "${root}/detach.log"
  grep -q "Detached ${expected_id} (${expected_busid})" "${root}/run.out"
)

# A capture that fails after attaching must return the keyboard to Windows.
run_failed_capture_case() (
  local root
  root="$(mktemp -d)"
  trap 'rm -rf "${root}"' EXIT
  make_fixture "${root}"
  touch "${root}/dump-fails"

  if TMP_STATE="${root}" \
    DWERTY_CAPTURE_DIR="${root}/out" \
    DWERTY_CAPTURE_TEST_MODE=1 \
    DWERTY_SETTLE_SECONDS=0 \
    DWERTY_USBIPD="${root}/usbipd.exe" \
    "${COLLECTOR}" "${root}/ultra" >"${root}/run.out" 2>"${root}/run.err"; then
    echo "Expected the capture to fail" >&2
    exit 1
  fi

  grep -q "detach --busid 9-3" "${root}/detach.log"
  ! compgen -G "${root}/out/*.jsonl" >/dev/null
  ! compgen -G "${root}/out/.dwerty-incident.*" >/dev/null
)

run_case "3434:d028" "9-3"
run_case "3434:0c60" "11-1" --hardware-id 3434:0C60
# A receiver that enumerates without answering must not shadow the wired path.
PRESET_MARKERS="mute-d028" run_case "3434:0c60" "11-1"
run_failed_capture_case
echo "Incident capture autodetection tests passed"
