# V6 Ultra diagnostic firmware and proof plan

The diagnostic build records the stages that can turn a physical key transition into a Windows modifier state. It is intended for a future controlled investigation. Nothing in this document requires touching or flashing deployed hardware now.

The trace is compiled out of normal release firmware. The ring-only build adds
a 1024-record RAM buffer and a private command on the existing Keychron
Launcher raw HID interface. The UART build also streams the same records
independently on UART2 from a dedicated low-priority thread.

Capture begins automatically when diagnostic firmware boots. `arm` clears the ring and establishes sequence zero; it does not enable tracing. Normal release firmware contains no trace buffer or diagnostic command. Diagnostic records remain only in RAM and are not transmitted until requested, but they contain physical key positions and timing and should be treated as sensitive input data.

## Build and collect

```bash
./scripts/build.sh --diagnostics
./scripts/package.sh --profile diagnostics
sudo ./scripts/scdfu.py flash --profile diagnostics

# Optional independent UART stream. Use only after the ring-only build because
# enabling UART changes timing, power and sleep behaviour.
./scripts/build.sh --diagnostics-uart
./scripts/package.sh --profile diagnostics-uart
```

The raw HID interface uses usage page `0xFF60`, usage `0x61`. It is available through the wired keyboard (`3434:0C60`) and through a compatible 2.4 GHz receiver path (`3434:D028`).

```bash
# List matching raw HID interfaces.
sudo scripts/diagnostics.py list

# Clear and arm the trace before a trial.
sudo scripts/diagnostics.py arm

# Insert a nonce in the device trace and record the matching Windows monotonic
# interval for correlation with USBPcap, ETW or Raw Input capture.
sudo scripts/diagnostics.py mark

# Freeze and dump the ring as JSON Lines after a fault.
sudo scripts/diagnostics.py dump --output trace.jsonl

# Validate raw-slot, decoded-event, anchor and sequence accounting.
scripts/diagnostics.py validate trace.jsonl

# Preferred incident command. It attaches through usbipd when needed, freezes
# immediately, validates and saves the trace, re-arms, then detaches from WSL.
scripts/capture-incident.sh

# Auto-detection prefers the known 2.4 GHz receiver, then wired USB. Override
# this for a different receiver or to force the direct keyboard path.
scripts/capture-incident.sh --hardware-id 3434:d028
scripts/capture-incident.sh --hardware-id 3434:0c60

# Preserve the in-device frozen trace or leave the wired interface in WSL.
scripts/capture-incident.sh --keep-frozen
scripts/capture-incident.sh --keep-attached

# Capture the independent 2 Mbaud UART2 stream.
uv run --with pyserial scripts/diagnostics.py serial --port COM5 > uart-trace.jsonl
```

The dump command freezes before reading, so ring indices cannot move during
extraction. The trace also freezes on kscan overflow, PPT overflow, PPT send
failure and modifier-count underflow. A report containing five or more
modifier bits arms a short post-trigger window, allowing the following queue
and send records to be retained before the ring freezes. A modifier held for
10 seconds freezes the ring from a timer, so a quiet latch does not require
another key event.

The ring is ordinary RAM, not retained storage. Do not power-cycle or reboot after a fault. Changing transport is equally destructive: unplugging the USB cable resets the keyboard and clears the ring. This was measured on hardware. A wired capture reported an uptime of 286 seconds, and a 2.4 GHz capture 143 seconds later reported an uptime of 18.5 seconds with an explicit `boot` record at 184 ms and a sequence counter restarted from zero. Always capture on whichever transport is already live when the fault appears, and never plug in a cable to obtain a more convenient connection. The reverse direction, attaching the cable while the keyboard runs on 2.4 GHz, has not been measured and should be assumed to reset the device until it is. The dump command freezes before its first read, so diagnostic responses cannot overwrite the captured ring even when extraction uses the 2.4 GHz path.

The ring is small relative to typing. One key transition costs about eight
records on the 2.4 GHz path and a modifier transition costs another record.
The 1024-slot protocol-2 ring holds roughly 60 typed characters after allowing
for periodic timing anchors. Collect the trace from a second keyboard or from
another host. Typing the collection command on the keyboard under
investigation destroys the window it is meant to preserve.

Bind the capture to a pointer-driven launcher so that collecting it costs no keystrokes at all. A Windows desktop shortcut targeting `cmd.exe /k wsl.exe -d <distribution> -- <path>/ultra/scripts/capture-incident.sh` reduces an incident capture to a double-click, and `/k` holds the result on screen until the window is closed with the mouse. Point `DWERTY_CAPTURE_DIR` at the same folder as the host-side evidence so the firmware trace and the Windows captures can be correlated by timestamp.

Trace files contain physical key positions and timing. Treat them as sensitive input data, minimise retention, and do not publish an unreviewed capture.

`scripts/capture-incident.sh` is the field runbook in executable form. It
recognises the known V6 Ultra wired PID `3434:0C60` and receiver PID
`3434:D028`, preferring the receiver so a wireless trace can be retrieved
without switching keyboard transport, which would reset the device and destroy
the trace. These are verified defaults for this hardware, not a universal
registry of Keychron receiver IDs. `--hardware-id VID:PID` supports an
explicit or future device. usbipd still requires a one-time elevated `bind`
for each Windows USB device before WSL can attach it. Given that one-time bind,
the attach, capture and detach cycle needs no manual usbipd step, verified on
hardware over both the wired and receiver paths.

The collector uses `diagnostics.py validate` before re-arming. The firmware
header counts raw slots, while decoded protocol-2 JSON omits `time_skip`
anchors, so a complete capture satisfies
`raw_slots = decoded_records + time_skip_records`. A validation failure
preserves the JSONL, writes a status sidecar, leaves the ring frozen and
detaches the selected device from WSL. Use `--keep-frozen` when a successful
capture's in-device copy must remain untouched. The sidecar records the source
commit and whether the working tree was dirty.

A dump freezes the ring, asks for its header, then reads every slot. It writes
that header to the output file straight away and marks it
`capture_status: partial`, so a link that drops mid-read still leaves the freeze
reason and ring counts on disk. The completed dump replaces that line with a
`capture_status: complete` header and the decoded records, so a capture never
carries two headers. A partial capture holds no records and never validates;
`validate` rejects it by status rather than letting an empty window pass as a
consistent one. Its `partial_error` names what stopped the read. A dump that
fails before the header is known writes nothing, and the sidecar reports
`capture_preserved=false` with `ring_remains_frozen=unknown`.

A candidate interface is selected only once it answers a diagnostic `info`
command. Attaching or detaching the receiver through usbipd drops and
re-establishes the keyboard's PPT link, measured on hardware as a `ppt_state`
transition to disconnected and back 775 ms after a detach, and the receiver
keeps exposing its raw HID interface throughout. Descriptor enumeration
therefore cannot show that the keyboard is reachable, and selecting on it
strands the capture on a path that forwards nothing. A freshly attached
interface is given `DWERTY_SETTLE_SECONDS`, 20 by default, to answer, and each
diagnostic command is retransmitted while that timeout runs, so a report lost
while the link settles costs a retry instead of the capture. A `read` reply is
accepted only when it echoes the requested record index, which keeps a
duplicated or late reply from being decoded as a different part of the ring. A
capture that fails after attaching writes the available status and detaches
the device again, because a stranded keyboard is unusable in Windows and the
next attempt would begin by reattaching it.

UART2 TX is configured on `P3_0`, with RX on `P3_1`, at 2,000,000 baud. The V6 Ultra shield overlay overrides the base board's UART2 pinctrl, and the generated devicetree resolves TX to pin 24 (`P3_0`). The existing debug GPIO is `GPIOA10`, labelled `P1_2` in the shield overlay. Confirm the physical pads and logic voltage against the board schematic before connecting equipment. Never drive a board signal from a 5 V adaptor.

The fork drives one column high at a time and samples the row inputs. The incident's common row is R5 on `GPIOA1` (`P0_1`). Its modifier columns are C0 on `GPIOB4` (`P3_7`), C1 on `GPIOB3` (`P3_6`), C2 on `GPIOB2` (`P3_5`) and C13 on `GPIOA16` (`MICBIAS`). A simple R5 input stuck high predicts activity across the full row, not only those four positions.

## Trace stages

| Event | Evidence |
|---|---|
| `matrix_raw` | A sampled electrical matrix state changed before debounce, reported in logical row/column orientation. |
| `kscan` | The debouncer emitted a row and column transition. |
| `position` | The matrix transform produced a ZMK position. |
| `keymap` | The position entered keymap resolution with its press-time default and active layer state. |
| `modifier` | A modifier reference count and explicit/report bitmask changed. |
| `hid_clear` | Endpoint handoff cleared the report, including the retained modifier state visible at that moment. |
| `hid_report` | The authoritative keyboard report immediately before transport, including the exact modifier byte and a CRC16 of the full report body. |
| `hid_send` | The endpoint accepted or rejected that report. |
| `ppt_queue` | The report entered the PPT queue, was rejected, or displaced an older report. |
| `ppt_tx` | The proprietary sync layer accepted or rejected a packet, with opcode, length and radio sequence. |
| `ppt_state` | The PPT connection state changed. |
| `endpoint` | The selected transport changed. |
| `mark` | A host nonce and device timestamp for cross-capture clock correlation. |

The trace also closes a smaller reliability gap found during this review: PPT callers now propagate a failed queue insertion rather than returning success after `ringbuf_msg_put()` failed. A non-zero `sync_msg_send()` result remains a recorded failure and still needs a retry-policy decision because the vendor API does not expose enough semantics to prove that blindly retrying is safe.

`hid_report.report_crc16` is CRC-16/CCITT-FALSE, initial value `0xFFFF`, over the report body beginning with the modifier byte. It can be recomputed from a parsed receiver USB report to correlate an internal send with a wire report without retaining typed key contents in the diagnostic trace.

The HID record deliberately does not retain key bytes. Use the preceding `position` and `keymap` events to identify the semantic key, and the HID CRC to match the complete report to a privacy-controlled USB capture.

## What would prove each layer

The four incident modifiers are all on row 5, but the HID modifier byte is independent of matrix topology. That gives the strongest discriminator.

| Observation | Supported conclusion |
|---|---|
| `matrix_raw` shows uncommanded row-5 transitions, including non-modifier row-5 keys, and a logic analyser or oscilloscope sees the same electrical assertion | The fault is at the switch, PCB, diode, row drive or GPIO input. Firmware is reporting the sampled hardware state. |
| Electrical probes remain clean, but `matrix_raw` reports a press | The first divergence is the MCU sampling or matrix driver, not the switch network. |
| Matrix and keymap records are clean, but modifier counts or `hid_report` form an unexplained modifier byte | The first divergence is keyboard firmware state. |
| The keyboard's `hid_report` is clean, but an inline USB capture from the receiver contains the bad modifier byte | The first divergence is after keyboard report formation, in PPT, RF or receiver firmware. |
| Receiver USB packets are clean, but Windows Raw Input or application state is wrong | The first divergence is in the host stack, a filter or the monitor's correlation. |

A raw matrix transition alone is not definitive hardware proof because a GPIO sampling or memory fault can fabricate it. Strong hardware attribution requires an independent electrical capture on the row drive and affected column inputs, synchronised with the trace.

## Future bench sequence

1. Capture a ring-only diagnostic trace and an inline USBPcap or hardware USB trace over wired USB and 2.4 GHz using the same automated key sequence.
2. Repeat with a golden keyboard and receiver, then cross-pair suspect and golden keyboards and receivers. A fault that follows the keyboard is upstream of the receiver; one that follows the receiver is downstream.
3. Test the complete row 5, including non-modifier keys, and modifiers on other rows. Row-following failures point to matrix hardware or scanning. Modifier-only failures point to report state or downstream handling.
4. Add a logic analyser on the R5 input (`GPIOA1`) and the C0, C1, C2 and C13 outputs (`GPIOB4`, `GPIOB3`, `GPIOB2`, `GPIOA16`). Use an oscilloscope on any line that shows an unexplained digital assertion to distinguish a hard short, leakage, slow settling and probe loading.
5. Use a mechanical actuator or open-drain electrical fixture for repeatable press and release timing. Sweep inter-key skew, Fn+Z or slide changes, queue load and RF attenuation while retaining identical controls.
6. Run large-N trials with randomised condition order and positive controls that deliberately lose a release. Report a rate bound when the incident does not reproduce rather than claiming exclusion.

The definitive result is the first stage where the observed state diverges from the independently measured stage below it. Reproducing a mechanism proves capability, not historical attribution, unless the reproduced trace matches the incident fingerprint and conditions.

Preserve the suspect unit as found. Capture receiver USB and external behaviour before opening it, then photograph the PCB and matrix area before cleaning or flexing. Moisture, contamination and whisker faults can disappear during disassembly.

## Windows evidence bundle

Capture the host and USB layers at the same time as the firmware trace. The `mark` command places a nonce in the device trace and reports the host monotonic interval containing the response, which can be matched to the vendor-HID transaction in the USB capture.

1. Start [USBPcap](https://desowin.org/usbpcap/) before inserting the receiver so enumeration, report descriptors and every interrupt-IN report are preserved. Parse reports from the captured descriptor rather than relying only on Wireshark's HID display.
2. Run Microsoft's [Windows bus tracing tools](https://github.com/microsoft/busiotools/tree/master/usb/tracing) with the input verbose profile to capture USB, HIDClass, keyboard-class and Virtual HID Framework providers.
3. Record Raw Input with the full `RAWKEYBOARD` fields, `hDevice`, `RIDI_DEVICENAME`, QueryPerformanceCounter and precise wall-clock time. Record a low-level keyboard hook and `GetAsyncKeyState` samples separately, because these observe different host layers.
4. Export the connected Keyboard, HIDClass and USB device trees with parent and container IDs. Save keyboard and HID class `UpperFilters` and `LowerFilters`, `pnputil /enum-drivers`, `pnputil /enum-devices /connected /class Keyboard /related`, and `driverquery /v /fo csv`.
5. Flag software or root-enumerated keyboards and Virtual HID Framework devices. `NotInjected` on a low-level hook does not exclude a kernel filter or virtual HID source.

An inline hardware USB analyser is stronger than USBPcap because it observes receiver wire output outside Windows. USBPcap showing a bad modifier byte proves that the host received it from the receiver, but cannot by itself distinguish keyboard firmware, RF transport and receiver firmware. Conversely, a clean USB transfer with a bad Raw Input or application state localises the divergence to Windows or software above the USB transport.
