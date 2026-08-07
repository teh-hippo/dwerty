# V6 Ultra diagnostic firmware and proof plan

The diagnostic build records the stages that can turn a physical key transition into a Windows modifier state. It is intended for a future controlled investigation. Nothing in this document requires touching or flashing deployed hardware now.

The trace is compiled out of normal release firmware. The ring-only build adds a 512-record RAM buffer and a private command on the existing Keychron Launcher raw HID interface. The UART build also streams the same records independently on UART2 from a dedicated low-priority thread.

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

# Preferred incident command. It attaches through usbipd when needed, freezes
# immediately, validates and saves the trace, re-arms, then detaches from WSL.
scripts/capture-incident.sh

# Preserve the in-device frozen trace or leave the wired interface in WSL.
scripts/capture-incident.sh --keep-frozen
scripts/capture-incident.sh --keep-attached

# Capture the independent 2 Mbaud UART2 stream.
uv run --with pyserial scripts/diagnostics.py serial --port COM5 > uart-trace.jsonl
```

The dump command freezes before reading, so ring indices cannot move during extraction. The trace also freezes on kscan overflow, PPT overflow, PPT send failure and modifier-count underflow. A report containing four or more modifier bits arms a short post-trigger window, allowing the following queue and send records to be retained before the ring freezes.

The ring is ordinary RAM, not retained storage. Do not power-cycle or reboot after a fault. Moving to wired mode without resetting the keyboard should leave the ring available for USB retrieval, but that preservation must be confirmed during the first controlled trial. The dump command freezes before its first read, so diagnostic responses cannot overwrite the captured ring even when extraction uses the 2.4 GHz path.

Trace files contain physical key positions and timing. Treat them as sensitive input data, minimise retention, and do not publish an unreviewed capture.

`scripts/capture-incident.sh` is the field runbook in executable form. It validates the complete JSONL file before re-arming, then detaches the keyboard from WSL so Windows regains wired access. Use `--keep-frozen` when the in-device copy must remain untouched. Copy the script to another machine if needed, or run the committed copy directly from the repository.

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
