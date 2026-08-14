#!/usr/bin/env python3
"""Read and decode the V6 Ultra diagnostic trace."""

import argparse
import collections
import datetime as dt
import glob
import json
import os
import pathlib
import re
import secrets
import select
import struct
import time


DEFAULT_VID = 0x3434
DEFAULT_PIDS = {0x0C60, 0xD028}
RAW_USAGE_PAGE = 0xFF60
RAW_USAGE = 0x61
RAW_DESCRIPTOR_SIGNATURE = b"\x06\x60\xff\x09\x61"
COMMAND = 0xD0
REPORT_SIZE = 32
RETRY_INTERVAL_MS = 250
RECORD_FORMAT = "<HBBIHH"
RECORD_SIZE = struct.calcsize(RECORD_FORMAT)
UART_MAGIC = b"\xD7\x59"
UART_FRAME_SIZE = 2 + RECORD_SIZE + 2

SUBCOMMANDS = {"info": 0, "read": 1, "arm": 2, "freeze": 3, "mark": 4}
EVENT_NAMES = {
    1: "boot",
    2: "arm",
    3: "matrix_raw",
    4: "kscan",
    5: "kscan_drop",
    6: "position",
    7: "keymap",
    8: "modifier",
    9: "hid_clear",
    10: "hid_report",
    11: "hid_send",
    12: "ppt_queue",
    13: "ppt_tx",
    14: "ppt_state",
    15: "endpoint",
    16: "freeze",
    17: "mark",
}
FREEZE_REASONS = {
    1: "host",
    2: "suspicious_modifiers",
    3: "kscan_overflow",
    4: "ppt_overflow",
    5: "ppt_send",
    6: "modifier_underflow",
}
TRANSPORTS = {0: "usb", 1: "ble", 2: "ppt"}
MODIFIERS = ("lctrl", "lshift", "lalt", "lgui", "rctrl", "rshift", "ralt", "rgui")
KEYMAP_NAME = "keychron_v6_ultra_ansi.keymap"
LAYER_PATTERN = re.compile(r"(\w+)\s*\{[^{}]*?(?<![-\w])bindings\s*=\s*<(.*?)>\s*;", re.S)


def crc16(data):
    crc = 0xFFFF
    for value in data:
        crc ^= value << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def signed16(value):
    return struct.unpack("<h", struct.pack("<H", value))[0]


def modifier_names(value):
    return [name for bit, name in enumerate(MODIFIERS) if value & (1 << bit)]


def decode_record(payload):
    sequence, event_type, flags, uptime_ms, arg0, arg1 = struct.unpack(RECORD_FORMAT, payload)
    result = {
        "sequence": sequence,
        "event": EVENT_NAMES.get(event_type, f"unknown_{event_type}"),
        "event_type": event_type,
        "flags": flags,
        "uptime_ms": uptime_ms,
        "arg0": arg0,
        "arg1": arg1,
    }
    pressed = bool(flags & 0x01)
    error = bool(flags & 0x02)

    if event_type in (3, 4, 5):
        result.update(row=arg0 & 0xFF, column=arg0 >> 8, pressed=pressed)
        if event_type == 4:
            result["queue_depth_before"] = arg1
        elif event_type == 5:
            result["result"] = signed16(arg1)
    elif event_type == 6:
        result.update(position=arg0, row=arg1 & 0xFF, column=arg1 >> 8, pressed=pressed)
    elif event_type == 7:
        result.update(
            position=arg0,
            default_layer=arg1 & 0xFF,
            active_layers=arg1 >> 8,
            pressed=pressed,
            source=flags >> 4,
        )
    elif event_type == 8:
        result.update(
            modifier=arg0 & 0xFF,
            count=arg0 >> 8,
            explicit_modifiers=arg1 & 0xFF,
            report_modifiers=arg1 >> 8,
            pressed=pressed,
            error=error,
        )
    elif event_type == 9:
        result.update(
            report_modifiers=arg0 & 0xFF,
            explicit_modifiers=arg0 >> 8,
            implicit_modifiers=arg1 & 0xFF,
            masked_modifiers=arg1 >> 8,
        )
    elif event_type == 10:
        modifiers = arg0 & 0xFF
        result.update(
            transport=TRANSPORTS.get(flags & 0x0F, flags & 0x0F),
            modifiers=modifiers,
            modifier_names=modifier_names(modifiers),
            reserved=arg0 >> 8,
            report_crc16=arg1,
        )
    elif event_type == 11:
        result.update(
            transport=TRANSPORTS.get(flags >> 4, flags >> 4),
            error=error,
            report_length=arg0,
            result=signed16(arg1),
        )
    elif event_type == 12:
        result.update(
            opcode=arg0 & 0xFF,
            value=arg1,
            error=error,
            discarded=bool(flags & 0x04),
        )
    elif event_type == 13:
        result.update(
            radio_sequence=flags >> 4,
            error=error,
            opcode=arg0 & 0xFF,
            packet_length=arg0 >> 8,
            result=signed16(arg1),
        )
    elif event_type == 14:
        result.update(connection_state=arg0, vendor_state=arg1)
    elif event_type == 15:
        result.update(
            old_transport=TRANSPORTS.get(arg0, arg0),
            new_transport=TRANSPORTS.get(arg1, arg1),
        )
    elif event_type == 16:
        result["reason"] = FREEZE_REASONS.get(arg0, arg0)
    elif event_type == 17:
        result["nonce"] = arg0 | (arg1 << 16)

    return result


def wall_clock(boot_at, uptime_ms):
    return (boot_at + dt.timedelta(milliseconds=uptime_ms)).isoformat()


def strip_comments(text):
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"//[^\n]*", " ", text)


def keymap_node(text):
    """Return the source of the `zmk,keymap` node, excluding behaviour definitions."""
    marker = text.find('compatible = "zmk,keymap"')
    if marker < 0:
        raise SystemExit("The keymap file contains no zmk,keymap node.")
    start = text.rfind("{", 0, marker)
    depth = 0
    for index in range(start, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start:index]
    raise SystemExit("The zmk,keymap node is not closed.")


def keymap_layers(path):
    """Return each layer's binding cells, indexed by the layer number the firmware reports."""
    node = keymap_node(strip_comments(pathlib.Path(path).read_text(encoding="utf-8")))
    layers = []
    for name, body in LAYER_PATTERN.findall(node):
        cells = [" ".join(("&" + cell).split()) for cell in body.split("&") if cell.strip()]
        layers.append({"layer": len(layers), "name": name, "bindings": cells})
    return layers


def binding_at(layers, layer, position):
    if position is None or layer is None:
        return None
    if layer < len(layers) and position < len(layers[layer]["bindings"]):
        return layers[layer]["bindings"][position]
    return None


def capture_boot(info):
    """Recover the device boot instant so records share a timebase with host logs."""
    if info.get("boot_at"):
        return dt.datetime.fromisoformat(info["boot_at"])
    if info.get("captured_at") and info.get("uptime_ms") is not None:
        captured = dt.datetime.fromisoformat(info["captured_at"])
        return captured - dt.timedelta(milliseconds=info["uptime_ms"])
    return None


def analyse_capture(objects, layers):
    """Report per-press evidence and the structural faults a capture can prove."""
    info = next((item for item in objects if item.get("kind") == "info"), {})
    records = [item for item in objects if item.get("kind") == "record"]
    boot_at = capture_boot(info)

    def moment(record):
        if record.get("recorded_at"):
            return record["recorded_at"]
        return wall_clock(boot_at, record["uptime_ms"]) if boot_at else None

    def describe(record=None, position=None, layer=None):
        record = record or {}
        if position is None:
            position = record.get("position")
        if layer is None:
            layer = record.get("default_layer")
        return {"position": position, "binding": binding_at(layers, layer, position)}

    raw_edges = collections.Counter()
    scan_edges = collections.Counter()
    positions = {}
    coordinates = {}
    scanned = set()
    released = set()
    repeats = []
    for record in records:
        key = (record.get("row"), record.get("column"))
        if record["event"] == "position":
            positions[key] = record["position"]
            coordinates[record["position"]] = key
        elif record["event"] == "matrix_raw":
            if record["pressed"]:
                raw_edges[key] += 1
            else:
                released.add(key)
        elif record["event"] == "kscan" and record["pressed"]:
            scan_edges[key] += 1
            if key in scanned and key not in released:
                repeats.append((key, record))
            scanned.add(key)
            released.discard(key)

    def reports_for_edge(index):
        """Count the reports a single key edge produced, before the next edge is routed."""
        count = 0
        for item in records[index + 1:]:
            if item["event"] == "keymap":
                break
            if item["event"] == "hid_report":
                count += 1
        return count

    presses = []
    anomalies = []
    held = {}
    reports = 0
    modifier_depth = 0
    default_layer = None
    for index, record in enumerate(records):
        event = record["event"]
        if event == "hid_report":
            reports += 1
        elif event == "modifier":
            modifier_depth = record["count"]
            if record["error"]:
                anomalies.append(
                    {
                        "anomaly": "modifier_error",
                        "at": moment(record),
                        "modifier": record["modifier"],
                        "count": record["count"],
                        "report_modifiers": record["report_modifiers"],
                    }
                )
        elif event == "kscan_drop":
            anomalies.append({"anomaly": "kscan_drop", "at": moment(record), **describe(record)})
        elif event == "keymap":
            default_layer = record["default_layer"]
            position = record["position"]
            if record["pressed"]:
                if position in held:
                    anomalies.append(
                        {
                            "anomaly": "press_without_release",
                            "at": moment(record),
                            **describe(record),
                        }
                    )
                held[position] = (index, record)
            elif position not in held:
                anomalies.append(
                    {"anomaly": "release_without_press", "at": moment(record), **describe(record)}
                )
            else:
                start_index, down = held.pop(position)
                key = coordinates.get(position)
                matrix = [
                    item
                    for item in records[start_index:index]
                    if item["event"] == "matrix_raw" and (item["row"], item["column"]) == key
                ]
                presses.append(
                    {
                        "kind": "press",
                        "at": moment(down),
                        "released_at": moment(record),
                        "held_ms": record["uptime_ms"] - down["uptime_ms"],
                        "layer": down["default_layer"],
                        "press_reports": reports_for_edge(start_index),
                        "release_reports": reports_for_edge(index),
                        "matrix_edges_while_down": len(matrix),
                        **describe(down),
                    }
                )

    for key, record in repeats:
        anomalies.append(
            {
                "anomaly": "repeat_without_raw_release",
                "at": moment(record),
                "row": key[0],
                "column": key[1],
                **describe(position=positions.get(key), layer=default_layer),
            }
        )

    for key, count in sorted(raw_edges.items()):
        if count > scan_edges[key]:
            anomalies.append(
                {
                    "anomaly": "contact_bounce_absorbed",
                    "row": key[0],
                    "column": key[1],
                    "raw_presses": count,
                    "debounced_presses": scan_edges[key],
                    **describe(position=positions.get(key), layer=default_layer),
                }
            )

    for position, (_, down) in sorted(held.items()):
        anomalies.append({"anomaly": "held_at_freeze", "at": moment(down), **describe(down)})

    summary = {
        "kind": "summary",
        "records": len(records),
        "window_start": moment(records[0]) if records else None,
        "window_end": moment(records[-1]) if records else None,
        "window_ms": records[-1]["uptime_ms"] - records[0]["uptime_ms"] if records else 0,
        "presses": len(presses),
        "hid_reports": reports,
        "overwritten": info.get("overwritten"),
        "freeze_reason": info.get("freeze_reason"),
        "trigger_reason": info.get("trigger_reason"),
        "boot_at": boot_at.isoformat() if boot_at else None,
        "boot_uncertainty_ms": info.get("boot_uncertainty_ms"),
        "modifier_depth_at_freeze": modifier_depth,
        "anomalies": collections.Counter(item["anomaly"] for item in anomalies),
    }
    return summary, presses, anomalies


def run_analyse(args):
    objects = [
        json.loads(line)
        for line in pathlib.Path(args.capture).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    keymap = args.keymap or pathlib.Path(__file__).parents[1] / "config" / KEYMAP_NAME
    layers = keymap_layers(keymap)
    summary, presses, anomalies = analyse_capture(objects, layers)
    summary["anomalies"] = dict(summary["anomalies"])
    emit(summary, None)
    if args.presses:
        for press in presses:
            emit(press, None)
    for anomaly in anomalies:
        emit({"kind": "anomaly", **anomaly}, None)


def parse_info(data):
    if len(data) != REPORT_SIZE or data[0] != COMMAND or data[2] != 0:
        raise RuntimeError(f"invalid diagnostic response: {data.hex()}")
    subcommand = data[1]
    result = {
        "protocol_version": data[3],
        "record_size": data[4],
        "capacity": struct.unpack_from("<H", data, 5)[0],
        "count": struct.unpack_from("<H", data, 7)[0],
        "next_sequence": struct.unpack_from("<H", data, 9)[0],
        "frozen": bool(data[11]),
        "freeze_reason": FREEZE_REASONS.get(data[12], data[12]),
        "overwritten": struct.unpack_from("<I", data, 13)[0],
        "uart_dropped": struct.unpack_from("<I", data, 17)[0],
        "uptime_ms": struct.unpack_from("<I", data, 21)[0],
        "trigger_remaining": data[25],
        "trigger_reason": FREEZE_REASONS.get(data[26], data[26]),
    }
    if subcommand == SUBCOMMANDS["mark"]:
        result["marker_nonce"] = struct.unpack_from("<I", data, 27)[0]
    else:
        result["next_sequence_absolute"] = struct.unpack_from("<I", data, 27)[0]
    return result


def echoes_request(subcommand, value, response):
    """Reject a stale reply that a retransmission or a slow link duplicated."""
    if subcommand == "read":
        return struct.unpack_from("<H", response, 4)[0] == value
    if subcommand == "mark":
        return struct.unpack_from("<I", response, 27)[0] == value
    return True


def import_hid(required=True):
    try:
        import hid
    except ImportError as error:
        if not required:
            return None
        raise SystemExit(
            "The hidapi module is required. Run with "
            "`uv run --with hidapi scripts/diagnostics.py ...`."
        ) from error
    return hid


def parse_hid_id(uevent):
    for line in uevent.splitlines():
        if not line.startswith("HID_ID="):
            continue
        try:
            _, vendor, product = line.split("=", 1)[1].split(":")
            return int(vendor, 16), int(product, 16)
        except ValueError:
            return None
    return None


def hidraw_devices(vid, pid):
    devices = []
    for sys_path in sorted(glob.glob("/sys/class/hidraw/hidraw*")):
        root = pathlib.Path(sys_path) / "device"
        try:
            uevent = (root / "uevent").read_text()
            descriptor = (root / "report_descriptor").read_bytes()
        except OSError:
            continue
        identity = parse_hid_id(uevent)
        if identity is None:
            continue
        vendor_id, product_id = identity
        if vendor_id != vid or (pid is not None and product_id != pid):
            continue
        if pid is None and product_id not in DEFAULT_PIDS:
            continue
        if RAW_DESCRIPTOR_SIGNATURE not in descriptor:
            continue
        properties = dict(
            line.split("=", 1) for line in uevent.splitlines() if "=" in line
        )
        devices.append(
            {
                "backend": "hidraw",
                "path": f"/dev/{pathlib.Path(sys_path).name}",
                "vendor_id": vendor_id,
                "product_id": product_id,
                "product_string": properties.get("HID_NAME"),
                "serial_number": properties.get("HID_UNIQ"),
                "usage_page": RAW_USAGE_PAGE,
                "usage": RAW_USAGE,
            }
        )
    return devices


def candidate_devices(vid, pid):
    direct = hidraw_devices(vid, pid)
    if direct:
        return direct

    hid = import_hid(required=False)
    if hid is None:
        return []
    devices = []
    for device in hid.enumerate(vid, pid or 0):
        if pid is None and device["product_id"] not in DEFAULT_PIDS:
            continue
        usage_page = device.get("usage_page") or 0
        usage = device.get("usage") or 0
        if usage_page not in (0, RAW_USAGE_PAGE) or usage not in (0, RAW_USAGE):
            continue
        devices.append(device)
    exact = [
        device
        for device in devices
        if device.get("usage_page") == RAW_USAGE_PAGE and device.get("usage") == RAW_USAGE
    ]
    return exact or devices


def device_summary(index, device):
    path = device["path"]
    path_text = path.decode(errors="replace") if isinstance(path, bytes) else str(path)
    return {
        "index": index,
        "vid": f"{device['vendor_id']:04x}",
        "pid": f"{device['product_id']:04x}",
        "product": device.get("product_string"),
        "serial": device.get("serial_number"),
        "usage_page": f"{(device.get('usage_page') or 0):04x}",
        "usage": f"{(device.get('usage') or 0):04x}",
        "path": path_text,
    }


class DiagnosticDevice:
    def __init__(self, device_info, timeout_ms):
        self._backend = device_info.get("backend", "hidapi")
        self._device = None
        self._fd = None
        if self._backend == "hidraw":
            try:
                self._fd = os.open(device_info["path"], os.O_RDWR | os.O_NONBLOCK)
            except PermissionError as error:
                raise SystemExit(
                    f"Permission denied opening {device_info['path']}; run this command with sudo."
                ) from error
            self._drain_hidraw()
        else:
            hid = import_hid()
            self._device = hid.device()
            self._device.open_path(device_info["path"])
        self._timeout_ms = timeout_ms

    def close(self):
        if self._fd is not None:
            os.close(self._fd)
        elif self._device is not None:
            self._device.close()

    def _drain_hidraw(self):
        while True:
            readable, _, _ = select.select((self._fd,), (), (), 0)
            if not readable:
                return
            os.read(self._fd, REPORT_SIZE + 1)

    def _write(self, request):
        report = bytes([0]) + request
        if self._fd is not None:
            written = os.write(self._fd, report)
        else:
            written = self._device.write(report)
        if written <= 0:
            raise RuntimeError("failed to write diagnostic command")

    def _read(self, timeout_ms):
        if self._fd is not None:
            readable, _, _ = select.select((self._fd,), (), (), timeout_ms / 1000)
            if not readable:
                return b""
            return os.read(self._fd, REPORT_SIZE + 1)
        return bytes(self._device.read(REPORT_SIZE + 1, timeout_ms))

    def exchange(self, subcommand, value=0):
        request = bytearray(REPORT_SIZE)
        request[0] = COMMAND
        request[1] = SUBCOMMANDS[subcommand]
        if subcommand == "mark":
            struct.pack_into("<I", request, 2, value)
        else:
            struct.pack_into("<H", request, 2, value)
        deadline = time.monotonic() + self._timeout_ms / 1000
        next_write = 0.0
        while True:
            now = time.monotonic()
            if now >= deadline:
                raise RuntimeError("timed out waiting for a matching diagnostic response")
            # A command sent while the link is still settling is dropped without
            # an error, so retransmit until the deadline expires.
            if now >= next_write:
                self._write(request)
                next_write = now + RETRY_INTERVAL_MS / 1000
            remaining_ms = max(1, int((min(next_write, deadline) - time.monotonic()) * 1000))
            response = bytes(self._read(remaining_ms))
            if len(response) == REPORT_SIZE + 1 and response[0] == 0:
                response = response[1:]
            if (
                len(response) == REPORT_SIZE
                and response[0] == COMMAND
                and response[1] == SUBCOMMANDS[subcommand]
                and echoes_request(subcommand, value, response)
            ):
                return response


def open_selected(args):
    devices = candidate_devices(args.vid, args.pid)
    if not devices:
        raise SystemExit("No matching Keychron Launcher raw HID interface was found.")
    if args.device >= len(devices):
        raise SystemExit(f"Device index {args.device} is out of range; use the `list` command.")
    return DiagnosticDevice(devices[args.device], args.timeout)


def emit(value, output):
    line = json.dumps(value, sort_keys=True)
    if output:
        output.write(line + "\n")
    else:
        print(line)


def run_hid_command(args):
    device = open_selected(args)
    output = pathlib.Path(args.output).open("w", encoding="utf-8") if args.output else None
    try:
        if args.command in ("info", "arm", "freeze"):
            info = parse_info(device.exchange(args.command))
            emit({"kind": "info", **info}, output)
            return
        if args.command == "mark":
            nonce = args.nonce if args.nonce is not None else secrets.randbits(32)
            before = time.perf_counter_ns()
            response = device.exchange("mark", nonce)
            after = time.perf_counter_ns()
            info = parse_info(response)
            emit(
                {
                    "kind": "mark",
                    "nonce": nonce,
                    "host_monotonic_before_ns": before,
                    "host_monotonic_after_ns": after,
                    **info,
                },
                output,
            )
            return

        device.exchange("freeze")
        before = dt.datetime.now(dt.timezone.utc)
        info = parse_info(device.exchange("info"))
        after = dt.datetime.now(dt.timezone.utc)
        boot_at = before + (after - before) / 2 - dt.timedelta(milliseconds=info["uptime_ms"])
        emit(
            {
                "kind": "info",
                "captured_at": after.isoformat(),
                "boot_at": boot_at.isoformat(),
                "boot_uncertainty_ms": (after - before) / dt.timedelta(milliseconds=1),
                **info,
            },
            output,
        )
        if info["record_size"] != RECORD_SIZE:
            raise RuntimeError(
                f"firmware record size {info['record_size']} does not match decoder {RECORD_SIZE}"
            )

        index = 0
        absolute_sequence = info["next_sequence_absolute"] - info["count"]
        while index < info["count"]:
            response = device.exchange("read", index)
            returned = response[3]
            if returned == 0:
                raise RuntimeError(f"firmware returned no records at index {index}")
            for offset in range(returned):
                start = 8 + offset * RECORD_SIZE
                record = decode_record(response[start:start + RECORD_SIZE])
                record["absolute_sequence"] = absolute_sequence + index + offset
                record["recorded_at"] = wall_clock(boot_at, record["uptime_ms"])
                emit({"kind": "record", **record}, output)
            index += returned
    finally:
        if output:
            output.close()
        device.close()


def run_serial(args):
    try:
        import serial
    except ImportError as error:
        raise SystemExit(
            "The pyserial module is required. Run with "
            "`uv run --with pyserial scripts/diagnostics.py serial ...`."
        ) from error

    buffer = bytearray()
    with serial.Serial(args.port, args.baud, timeout=0.1) as port:
        while True:
            buffer.extend(port.read(256))
            while True:
                marker = buffer.find(UART_MAGIC)
                if marker < 0:
                    del buffer[:-1]
                    break
                if marker:
                    del buffer[:marker]
                if len(buffer) < UART_FRAME_SIZE:
                    break
                frame = bytes(buffer[:UART_FRAME_SIZE])
                expected = struct.unpack_from("<H", frame, UART_FRAME_SIZE - 2)[0]
                if crc16(frame[:-2]) != expected:
                    del buffer[:1]
                    continue
                del buffer[:UART_FRAME_SIZE]
                emit(
                    {
                        "kind": "record",
                        "captured_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                        **decode_record(frame[2:2 + RECORD_SIZE]),
                    },
                    None,
                )


def parse_int(value):
    return int(value, 0)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--vid", type=parse_int, default=DEFAULT_VID)
    parser.add_argument("--pid", type=parse_int)
    parser.add_argument("--device", type=int, default=0)
    parser.add_argument("--timeout", type=int, default=2000)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list")
    for command in ("info", "arm", "freeze"):
        command_parser = subparsers.add_parser(command)
        command_parser.add_argument("--output")
    mark_parser = subparsers.add_parser("mark")
    mark_parser.add_argument("--nonce", type=parse_int)
    mark_parser.add_argument("--output")
    dump_parser = subparsers.add_parser("dump")
    dump_parser.add_argument("--output")
    serial_parser = subparsers.add_parser("serial")
    serial_parser.add_argument("--port", required=True)
    serial_parser.add_argument("--baud", type=int, default=2_000_000)
    analyse_parser = subparsers.add_parser("analyse")
    analyse_parser.add_argument("capture")
    analyse_parser.add_argument("--keymap")
    analyse_parser.add_argument("--presses", action="store_true")

    args = parser.parse_args()
    if args.command == "list":
        for index, device in enumerate(candidate_devices(args.vid, args.pid)):
            print(json.dumps(device_summary(index, device), sort_keys=True))
    elif args.command == "serial":
        run_serial(args)
    elif args.command == "analyse":
        run_analyse(args)
    else:
        run_hid_command(args)


if __name__ == "__main__":
    main()
