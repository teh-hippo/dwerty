#!/usr/bin/env bash

set -euo pipefail

ULTRA_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COLLECTOR="${ULTRA_DIR}/scripts/capture-incident.sh"

# `set -e` exempts a command whose status is inverted with `!`, so a negative
# assertion written that way passes even when the condition it guards is true.
refute() {
  local description="$1"
  shift
  if "$@" >/dev/null 2>&1; then
    echo "Expected no ${description}" >&2
    exit 1
  fi
}

make_fixture() {
  local root="$1"
  mkdir -p "${root}/ultra/scripts" "${root}/out"

  cat >"${root}/ultra/scripts/diagnostics.py" <<'EOF'
#!/usr/bin/env bash
pid=""
command=""
output=""
capture=""
while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --pid) pid="$2"; shift ;;
    list|arm|dump|info|validate|analyse) command="$1" ;;
    --output) output="$2"; shift ;;
    *) [[ "${command}" == "validate" || "${command}" == "analyse" ]] && capture="$1" ;;
  esac
  shift
done
echo "${command}" >>"${TMP_STATE}/subcommands.log"
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
    if [[ -f "${TMP_STATE}/dump-fails-partial" ]]; then
      header='{"kind":"info","frozen":true,"protocol_version":2,"count":4,'
      header+='"capture_status":"partial","raw_slots":2,"freeze_reason":"host",'
      header+='"partial_error":"timed out waiting for a matching diagnostic response"}'
      printf '%s\n' "${header}" >"${output}"
      exit 1
    fi
    if [[ -f "${TMP_STATE}/protocol2" ]]; then
      header='{"kind":"info","frozen":true,"protocol_version":2,"count":4,'
      header+='"raw_slots":4,"decoded_records":2,"time_skip_records":2,'
      header+='"uptime_unknown_records":0,"next_sequence_absolute":104}'
      printf '%s\n' \
        "${header}" \
        '{"kind":"record","absolute_sequence":101}' \
        '{"kind":"record","absolute_sequence":103}' >"${output}"
    else
      header='{"kind":"info","frozen":true,"protocol_version":1,"count":1,'
      header+='"raw_slots":1,"decoded_records":1,"time_skip_records":0,'
      header+='"uptime_unknown_records":0,"next_sequence_absolute":1}'
      printf '%s\n' \
        "${header}" \
        '{"kind":"record","absolute_sequence":0}' >"${output}"
    fi
    ;;
  validate)
    if [[ -f "${TMP_STATE}/validation-fails" ]]; then
      echo '{"kind":"validation","valid":false,"error":"synthetic failure"}'
      exit 1
    fi
    if [[ -f "${TMP_STATE}/protocol2" ]]; then
      echo '{"kind":"validation","valid":true,"protocol_version":2,"raw_slots":4,"decoded_records":2,"time_skip_records":2}'
    else
      echo '{"kind":"validation","valid":true,"protocol_version":1,"raw_slots":1,"decoded_records":1,"time_skip_records":0}'
    fi
    ;;
  analyse) ;;
  arm)
    touch "${TMP_STATE}/armed"
    echo '{"kind":"info","count":1}'
    ;;
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
  grep -q "^repository_dirty=unknown$" "${root}"/out/*.txt
  grep -q "^capture_status=validated$" "${root}"/out/*.txt
  grep -q "^ring_rearmed=true$" "${root}"/out/*.txt
  grep -q '"valid":true' "${root}"/out/*.txt
  [[ -f "${root}/armed" ]]
  grep -q "detach --busid ${expected_busid}" "${root}/detach.log"
  grep -q "Detached ${expected_id} (${expected_busid})" "${root}/run.out"

  # Collection records evidence. It states the layer it covers and where the
  # files went, and leaves interpretation to a command the operator runs later.
  grep -q "^dump$" "${root}/subcommands.log"
  grep -q "^validate$" "${root}/subcommands.log"
  refute "analyse subcommand" grep -q "^analyse$" "${root}/subcommands.log"
  refute "analysis in the sidecar" grep -q "analysis_begin" "${root}"/out/*.txt
  refute "analysis on stdout" grep -qi "^Analysis:" "${root}/run.out"
  grep -q "^evidence_layer=keyboard$" "${root}"/out/*.txt
  grep -q "^evidence_excludes=radio,receiver,receiver_usb,windows$" "${root}"/out/*.txt
  grep -q "^analyse_command=.* analyse .*\.jsonl$" "${root}"/out/*.txt
  grep -q "^schema_command=.* schema$" "${root}"/out/*.txt
  grep -q "does not cover radio delivery" "${root}/run.out"
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
  refute "preserved capture" compgen -G "${root}/out/*.jsonl"
  grep -q "^capture_status=dump_failed$" "${root}"/out/*.txt
  grep -q "^capture_preserved=false$" "${root}"/out/*.txt
  grep -q "^ring_rearmed=false$" "${root}"/out/*.txt
  grep -q "^ring_remains_frozen=unknown$" "${root}"/out/*.txt
  [[ ! -f "${root}/armed" ]]
  refute "temporary file" compgen -G "${root}/out/.dwerty-incident.*"
)

# A dump that stops part way through leaves the partial header it wrote once the
# ring froze, which names the freeze reason. That is evidence and outlives the
# failure. It never validates, because the records behind it were never read.
run_partial_dump_case() (
  local root
  root="$(mktemp -d)"
  trap 'rm -rf "${root}"' EXIT
  make_fixture "${root}"
  touch "${root}/dump-fails-partial"

  if TMP_STATE="${root}" \
    DWERTY_CAPTURE_DIR="${root}/out" \
    DWERTY_CAPTURE_TEST_MODE=1 \
    DWERTY_SETTLE_SECONDS=0 \
    DWERTY_USBIPD="${root}/usbipd.exe" \
    "${COLLECTOR}" "${root}/ultra" >"${root}/run.out" 2>"${root}/run.err"; then
    echo "Expected the capture to fail" >&2
    exit 1
  fi

  compgen -G "${root}/out/*.jsonl" >/dev/null
  grep -q '"capture_status":"partial"' "${root}"/out/*.jsonl
  grep -q '"freeze_reason":"host"' "${root}"/out/*.jsonl
  grep -q "^capture_status=dump_failed$" "${root}"/out/*.txt
  grep -q "^capture_preserved=true$" "${root}"/out/*.txt
  grep -q "^capture_partial=true$" "${root}"/out/*.txt
  grep -q "^capture_validated=false$" "${root}"/out/*.txt
  grep -q "^ring_rearmed=false$" "${root}"/out/*.txt
  grep -q "^ring_remains_frozen=true$" "${root}"/out/*.txt
  [[ ! -f "${root}/armed" ]]
  refute "temporary file" compgen -G "${root}/out/.dwerty-incident.*"
  grep -q "detach --busid 9-3" "${root}/detach.log"
)

run_failed_validation_case() (
  local root
  root="$(mktemp -d)"
  trap 'rm -rf "${root}"' EXIT
  make_fixture "${root}"
  touch "${root}/validation-fails"

  if TMP_STATE="${root}" \
    DWERTY_CAPTURE_DIR="${root}/out" \
    DWERTY_CAPTURE_TEST_MODE=1 \
    DWERTY_SETTLE_SECONDS=0 \
    DWERTY_USBIPD="${root}/usbipd.exe" \
    "${COLLECTOR}" "${root}/ultra" >"${root}/run.out" 2>"${root}/run.err"; then
    echo "Expected validation to fail" >&2
    exit 1
  fi

  compgen -G "${root}/out/*.jsonl" >/dev/null
  grep -q "^capture_status=validation_failed$" "${root}"/out/*.txt
  grep -q "^ring_rearmed=false$" "${root}"/out/*.txt
  grep -q "^ring_remains_frozen=true$" "${root}"/out/*.txt
  grep -q '"valid":false' "${root}"/out/*.txt
  [[ ! -f "${root}/armed" ]]
  grep -q "detach --busid 9-3" "${root}/detach.log"
)

run_keep_frozen_case() (
  local root
  root="$(mktemp -d)"
  trap 'rm -rf "${root}"' EXIT
  make_fixture "${root}"
  touch "${root}/protocol2"

  TMP_STATE="${root}" \
    DWERTY_CAPTURE_DIR="${root}/out" \
    DWERTY_CAPTURE_TEST_MODE=1 \
    DWERTY_SETTLE_SECONDS=0 \
    DWERTY_USBIPD="${root}/usbipd.exe" \
    "${COLLECTOR}" --keep-frozen "${root}/ultra" >"${root}/run.out"

  grep -q "^ring_rearmed=false$" "${root}"/out/*.txt
  grep -q "^ring_remains_frozen=true$" "${root}"/out/*.txt
  grep -q '"protocol_version":2' "${root}"/out/*.txt
  [[ ! -f "${root}/armed" ]]
)

run_keep_attached_case() (
  local root
  root="$(mktemp -d)"
  trap 'rm -rf "${root}"' EXIT
  make_fixture "${root}"

  TMP_STATE="${root}" \
    DWERTY_CAPTURE_DIR="${root}/out" \
    DWERTY_CAPTURE_TEST_MODE=1 \
    DWERTY_SETTLE_SECONDS=0 \
    DWERTY_USBIPD="${root}/usbipd.exe" \
    "${COLLECTOR}" --keep-attached "${root}/ultra" >"${root}/run.out"

  grep -q "^ring_rearmed=true$" "${root}"/out/*.txt
  [[ -f "${root}/armed" ]]
  [[ ! -f "${root}/detach.log" ]]
  grep -q "left attached to WSL" "${root}/run.out"
)

run_case "3434:d028" "9-3"
run_case "3434:0c60" "11-1" --hardware-id 3434:0C60
# A receiver that enumerates without answering must not shadow the wired path.
PRESET_MARKERS="mute-d028" run_case "3434:0c60" "11-1"
PRESET_MARKERS="protocol2" run_case "3434:d028" "9-3"
run_failed_capture_case
run_partial_dump_case
run_failed_validation_case
run_keep_frozen_case
run_keep_attached_case
echo "Incident capture autodetection tests passed"
