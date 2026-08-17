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
# Protocol 2 packs the same fields into 7 bytes. The sequence is dropped because
# a ring position already determines it, and the absolute uptime becomes an
# 11-bit delta, because 77% of consecutive records share a millisecond. A delta
# too large for that field is carried by a preceding time_skip record.
RECORD_SIZE_V2 = 7
TIME_DELTA_BITS = 11
TIME_DELTA_ESCAPE = (1 << TIME_DELTA_BITS) - 1
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
    18: "time_skip",
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
# The shield composes a direct-GPIO kscan at row-offset 6 for the Mac/Win slide,
# the transport selectors, USB detection and charging. Those inputs hold their
# state indefinitely by design, so they are device state rather than keystrokes.
STATE_ROW = 6

# Every observation names the pipeline layer it was seen at, because the trace
# ends at the keyboard and a reader has to know which layers it says nothing
# about before drawing a conclusion from one.
OBSERVATIONS = {
    "contact_bounce_absorbed": {
        "layer": "matrix",
        "means": "A switch bounced and the debouncer filtered it. Switch wear, "
                 "not an output error.",
    },
    "repeat_without_raw_release": {
        "layer": "debounce",
        "means": "A debounced repeat arrived while the raw matrix still read closed, "
                 "which no second physical press can produce.",
    },
    "press_without_release": {
        "layer": "keymap",
        "means": "A position was routed as pressed twice with no release between.",
    },
    "release_without_press": {
        "layer": "keymap",
        "means": "A release was routed for a position not held, and the window "
                 "retained the span the press would have occupied.",
    },
    "modifier_error": {
        "layer": "hid_state",
        "means": "The firmware's modifier reference count underflowed.",
    },
    "kscan_drop": {
        "layer": "scan_queue",
        "means": "The scan queue discarded a transition.",
    },
    "transport_error": {
        "layer": "keyboard_transport",
        "means": "A queue, transmit or send stage errored or discarded on the "
                 "keyboard side of the link. Its absence says the keyboard handed "
                 "the report over; it does not show that the radio, receiver, "
                 "receiver USB or Windows delivered it.",
    },
}

EVIDENCE_BOUNDARY = {
    "layer": "keyboard",
    "covers": "MCU matrix sampling through the keyboard's hand-off of a HID report "
              "to a transport.",
    "excludes": [
        "radio delivery",
        "receiver firmware",
        "receiver USB",
        "the Windows input stack",
        "the application receiving input",
        "records overwritten before the window opened",
        "anything after the ring froze",
    ],
    "reading": "The observation set is scoped to the layers above, across the retained "
               "window only. An empty set means nothing inconsistent was recorded there, "
               "which is consistent with a fault at any excluded layer and with a fault "
               "outside the window.",
}

# Which cell identity may be rendered without asking. A modifier, a layer switch
# and a keyboard-local control carry no typed content and are the investigation's
# subject; an ordinary key's identity is typed content.
BINDING_CLASSES = {
    "modifier": "A modifier, held or sticky. Rendered because it is the subject.",
    "layer": "A layer switch. Rendered because routing depends on it.",
    "control": "A keyboard-local control such as lighting, transport selection or "
               "pairing, which emits no keystroke.",
    "device_state": "A direct GPIO input such as the Mac/Win slide or a transport "
                    "selector. Rendered because it is device state, not input.",
    "morph_key": "A Dwerty mod-morph, whose identity is a typed character.",
    "key": "An ordinary key, whose identity is a typed character.",
    "unassigned": "The position holds no binding on the reported layer.",
}
REVEALED_CLASSES = ("modifier", "layer", "control", "device_state", "unassigned")
MODIFIER_BEHAVIOURS = ("&kp", "&sk", "&uc")
LAYER_BEHAVIOURS = ("&mo", "&to", "&tog", "&lt", "&sl", "&df")
CONTROL_BEHAVIOURS = ("&kc", "&kc_lp", "&rgb_ug", "&bl", "&bt", "&out", "&ext_power")
CONTROL_PREFIXES = ("&bt_pair", "&bt_recon", "&ppt_pair", "&rgb_")
MODIFIER_KEYCODES = {
    "LCTRL", "LCTL", "LEFT_CONTROL", "RCTRL", "RCTL", "RIGHT_CONTROL",
    "LSHIFT", "LSHFT", "LEFT_SHIFT", "RSHIFT", "RSHFT", "RIGHT_SHIFT",
    "LALT", "LEFT_ALT", "RALT", "RIGHT_ALT",
    "LGUI", "LWIN", "LCMD", "LMETA", "LEFT_GUI", "LEFT_WIN", "LEFT_COMMAND", "LEFT_META",
    "RGUI", "RWIN", "RCMD", "RMETA", "RIGHT_GUI", "RIGHT_WIN", "RIGHT_COMMAND", "RIGHT_META",
}


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


def pack_record_v2(event_type, flags, delta_ms, arg0, arg1):
    """Pack one protocol 2 record. Only the time delta straddles a byte boundary."""
    if not 0 <= delta_ms <= TIME_DELTA_ESCAPE:
        raise ValueError(f"time delta {delta_ms} does not fit in {TIME_DELTA_BITS} bits")
    payload = bytearray(RECORD_SIZE_V2)
    payload[0] = (event_type & 0x1F) | ((delta_ms >> 8) << 5)
    payload[1] = delta_ms & 0xFF
    payload[2] = flags & 0xFF
    struct.pack_into("<HH", payload, 3, arg0 & 0xFFFF, arg1 & 0xFFFF)
    return bytes(payload)


def unpack_record_v2(payload):
    event_type = payload[0] & 0x1F
    delta_ms = ((payload[0] >> 5) << 8) | payload[1]
    arg0, arg1 = struct.unpack_from("<HH", payload, 3)
    return event_type, payload[2], delta_ms, arg0, arg1


TIME_SKIP_CONTINUOUS = 0x01


def encode_records_v2(records, anchor_interval=64):
    """Encode decoded records to protocol 2, mirroring the firmware's anchoring."""
    stream = bytearray()
    previous = None
    since_anchor = 0
    for record in records:
        uptime = record["uptime_ms"]
        delta = 0 if previous is None else uptime - previous
        continuous = previous is not None and 0 <= delta < TIME_DELTA_ESCAPE
        if not continuous or since_anchor >= anchor_interval:
            stream += pack_record_v2(
                18,
                TIME_SKIP_CONTINUOUS if continuous else 0,
                TIME_DELTA_ESCAPE,
                uptime & 0xFFFF,
                (uptime >> 16) & 0xFFFF,
            )
            since_anchor = 0
            if not continuous:
                delta = 0
        since_anchor += 1
        stream += pack_record_v2(
            record["event_type"], record["flags"], delta, record["arg0"], record["arg1"]
        )
        previous = uptime
    return bytes(stream)


def decode_records_v2(stream, uptime_ms=0, sequence=0, with_stats=False):
    """Decode a protocol 2 stream, restoring absolute uptime and sequence.

    A wrapped ring can begin part way through, so an anchor stamps the record
    that follows it and the records before the first anchor are recovered by
    walking their own deltas backwards.
    """
    entries = [
        unpack_record_v2(stream[offset:offset + RECORD_SIZE_V2])
        for offset in range(0, len(stream) - RECORD_SIZE_V2 + 1, RECORD_SIZE_V2)
    ]

    def is_anchor(entry):
        return entry[0] == 18 and entry[2] == TIME_DELTA_ESCAPE

    times = {}
    stamped = None
    running = None
    for index, entry in enumerate(entries):
        if is_anchor(entry):
            stamped = entry[3] | (entry[4] << 16)
            continue
        if stamped is not None:
            running = stamped
            stamped = None
        elif running is not None:
            running += entry[2]
        if running is not None:
            times[index] = running

    emitted = [index for index, entry in enumerate(entries) if not is_anchor(entry)]
    if not times:
        running = uptime_ms
        for index in emitted:
            running += entries[index][2]
            times[index] = running
    else:
        # Walk back through the leading records, stopping where an anchor says
        # the delta it displaced could not be kept.
        for position in range(len(emitted) - 1, 0, -1):
            index, previous_index = emitted[position], emitted[position - 1]
            if previous_index in times or index not in times:
                continue
            broken = any(
                is_anchor(entries[between]) and not entries[between][1] & TIME_SKIP_CONTINUOUS
                for between in range(previous_index + 1, index)
            )
            if not broken:
                times[previous_index] = times[index] - entries[index][2]

    records = []
    for index in emitted:
        event_type, flags, _, arg0, arg1 = entries[index]
        # A sequence identifies a ring slot, and an anchor occupies one, so the
        # stored index is what numbers a record rather than its output position.
        absolute = sequence + index
        record = decode_record(
            struct.pack(
                RECORD_FORMAT,
                absolute & 0xFFFF,
                event_type,
                flags,
                times.get(index, 0),
                arg0,
                arg1,
            )
        )
        record["absolute_sequence"] = absolute
        if index not in times:
            record["uptime_unknown"] = True
        records.append(record)
    stats = {
        "raw_slots": len(entries),
        "decoded_records": len(records),
        "time_skip_records": len(entries) - len(emitted),
        "uptime_unknown_records": sum(
            1 for record in records if record.get("uptime_unknown")
        ),
    }
    if with_stats:
        return records, stats
    return records


def capture_schema():
    """Describe a capture well enough to be read without this source."""
    return {
        "read_me_first": [
            "A capture is a window cut from a ring, not a recording of an incident. "
            "Check overwritten and freeze_reason before reading anything into it.",
            "This tool records evidence and measures it. It does not decide whether an "
            "incident occurred. That needs the raw timing here, the operator's account "
            "and evidence from the layers named in evidence_boundary.",
            "keyboard_observations lists what the keyboard's own records are inconsistent "
            "about, at the layer each observation names. at_freeze, truncated_releases and "
            "device_state are where the window starts and stops, not faults.",
        ],
        "protocol": {
            1: {
                "record_size": RECORD_SIZE,
                "layout": "little endian: sequence u16, event_type u8, flags u8, "
                          "uptime_ms u32, arg0 u16, arg1 u16",
            },
            2: {
                "record_size": RECORD_SIZE_V2,
                "layout": "byte0 = event_type[4:0] | time_delta[10:8] << 5, "
                          "byte1 = time_delta[7:0], byte2 = flags, "
                          "bytes3-4 = arg0 u16 le, bytes5-6 = arg1 u16 le",
                "time": "time_delta_ms is relative to the previous record. A delta of "
                        f"{TIME_DELTA_ESCAPE} marks a time_skip record whose arg0 and arg1 "
                        "carry the next absolute uptime_ms as a u32.",
                "sequence": "Not stored. A record's position in the ring determines it, "
                            "so the decoder restores the same values protocol 1 stored.",
            },
        },
        "capture_header": {
            "capture_status": "complete once every ring slot was read and decoded. "
                              "partial when the dump froze the ring but the read or decode "
                              "failed, in which case the header stands alone with no records "
                              "and carries partial_error.",
            "count": "Raw ring slots reported by the firmware. Protocol records such as "
                     "time_skip anchors are included.",
            "raw_slots": "Raw slots read from the device. Equal to count for a complete dump.",
            "decoded_records": "Event records emitted to JSONL after protocol records are "
                               "consumed.",
            "time_skip_records": "Protocol 2 anchor slots consumed by the decoder and not "
                                 "emitted as events.",
            "uptime_unknown_records": "Decoded events whose wall-clock time cannot be "
                                      "reconstructed without inventing a timestamp.",
        },
        "validation": {
            "valid": "True only when the JSONL structure, counts, and absolute sequence "
                     "coverage are internally consistent. A partial capture never validates.",
            "method": "header_stats for current captures, legacy_protocol_1 or "
                      "legacy_protocol_2_sequence for older captures.",
            "relationship": "raw_slots = decoded_records + time_skip_records",
        },
        "units": {
            "uptime_ms": "milliseconds since boot",
            "held_ms": "milliseconds",
            "recorded_at": "ISO 8601 UTC, derived from boot_at plus uptime_ms",
            "boot_at": "ISO 8601 UTC, device uptime bracketed against the host clock",
            "boot_uncertainty_ms": "width of that bracket",
        },
        "events": {
            "boot": "Firmware started. Records before it belong to an earlier run.",
            "arm": "The ring was cleared and started recording.",
            "matrix_raw": "A raw electrical transition, before debounce. row, column, pressed.",
            "kscan": "A debounced transition the driver accepted. Adds queue_depth_before.",
            "kscan_drop": "The scan queue discarded a transition. Adds result.",
            "position": "A matrix coordinate resolved to a keymap position.",
            "keymap": "A position routed to a binding. Adds default_layer, active_layers, source.",
            "modifier": "The modifier refcount changed. Adds explicit_modifiers, report_modifiers.",
            "hid_clear": "Modifiers were masked or cleared before a report.",
            "hid_report": "A HID report was formed. Adds modifiers and report_crc16.",
            "hid_send": "A report was handed to a transport. Adds report_length, result.",
            "ppt_queue": "A report entered the 2.4 GHz queue. discarded marks an overflow drop.",
            "ppt_tx": "A radio packet was transmitted. Adds radio_sequence, packet_length, result.",
            "ppt_state": "The radio connection or vendor state changed.",
            "endpoint": "The active transport changed.",
            "freeze": "Recording stopped. reason names the cause.",
            "mark": "A host correlation marker carrying a nonce.",
            "time_skip": "Protocol 2 only. An anchor holding an absolute uptime, stored "
                         "every 64 records and whenever a delta will not fit, so a wrapped "
                         "window can still be dated. Not emitted in decoded output.",
        },
        "matrix": {
            "state_row": STATE_ROW,
            "note": "The shield composes a direct GPIO kscan at this row offset for the "
                    "Mac/Win slide, transport selectors, USB detection and charging. Those "
                    "inputs hold state indefinitely and are not keystrokes.",
        },
        "freeze_reasons": FREEZE_REASONS,
        "transports": TRANSPORTS,
        "modifiers": list(MODIFIERS),
        "summary": {
            "capture_status": "Mirrors the header. A partial summary counts nothing "
                              "because the records were never read, not because the "
                              "keyboard behaved.",
            "presses": "Key presses matched to a release within the capture.",
            "hid_reports": "HID reports the firmware formed.",
            "overwritten": "Records already lost to ring wrap. Non-zero means the capture is "
                           "a window, so absence of an event proves nothing.",
            "peak_modifiers": "The most modifiers the keyboard placed in one report. A count "
                              "alone does not separate a chord from a fault; read it with "
                              "modifier_activity.",
            "longest_modifier_hold": "The longest any single modifier stayed set.",
            "modifier_activity": "How tightly modifiers arrived. See the modifier_activity "
                                 "section.",
            "at_freeze": "Keys and modifiers still held when recording stopped. Boundary "
                         "state, not a fault: judge it by held_ms. A ring frozen on five "
                         "modifiers necessarily reports five modifiers held.",
            "truncated_releases": "Releases whose press was overwritten before the window.",
            "device_state": "Direct GPIO inputs held at the freeze.",
            "keyboard_observations": "Counts of what the keyboard's own records are "
                                     "inconsistent about, each scoped to the layer it names. "
                                     "An empty set is scoped the same way: see "
                                     "evidence_boundary before reading it as an all-clear.",
            "evidence_boundary": "The layers this capture covers and the layers it says "
                                 "nothing about.",
            "key_identity": "classified when ordinary key identity was withheld, revealed "
                            "when --reveal-keys rendered it.",
        },
        "modifier_activity": {
            "purpose": "Cadence is what separates a chord a person typed from modifiers "
                       "that arrived together. Peak count and hold duration read alike for "
                       "both, so the intervals are measured rather than inferred.",
            "assertions": "Modifier bits that went from clear to set across hid_report "
                          "records in the window.",
            "distinct_modifiers": "How many different modifiers were asserted.",
            "shortest_gap_ms": "The shortest interval between consecutive assertions of two "
                               "different modifiers.",
            "tightest_burst": "The widest run of distinct modifiers that arrived without one "
                              "repeating, taking the shortest such run when several tie. "
                              "Carries count, span_ms, modifiers and at.",
            "interpretation": "None is applied. A span of a few hundred milliseconds and a "
                              "span of tens of milliseconds are both reported as measured.",
        },
        "observations": {
            name: {"layer": entry["layer"], "means": entry["means"]}
            for name, entry in OBSERVATIONS.items()
        },
        "privacy": {
            "boundary": "An ordinary key's identity is typed content and is not the "
                        "investigation's subject, so it is withheld by default. A capture's "
                        "positions reconstruct typed input once they are read against a "
                        "published keymap, so treat a capture as sensitive whether or not "
                        "identity was rendered.",
            "always_reported": [
                "position",
                "matrix row and column, wherever the capture resolved one",
                "press and release state",
                "held_ms and every other timing field",
                "reports formed per edge",
                "pipeline progression across events",
            ],
            "binding_class": BINDING_CLASSES,
            "rendered_without_asking": list(REVEALED_CLASSES),
            "reveal": "analyse --reveal-keys renders key and morph_key identity too.",
        },
        "evidence_boundary": EVIDENCE_BOUNDARY,
        "limits": [
            "The trace shows what the MCU read and what the firmware sent. It cannot "
            "distinguish a switch a person pressed from an intersection read as closed "
            "for electrical reasons.",
            "It ends at the keyboard. A receiver USB capture is needed for the radio and "
            "host stages, and a keyboard-side send reported as successful does not show "
            "that the radio, receiver or Windows delivered it.",
            "It cannot say whether an incident occurred. It says what the keyboard "
            "recorded across the window it retained.",
        ],
    }


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


def classify_binding(binding, row=None):
    """Sort a binding cell into the classes the privacy boundary is drawn around."""
    if row == STATE_ROW:
        return "device_state"
    if not binding or binding in ("&none", "&trans"):
        return "unassigned"
    behaviour, _, argument = binding.partition(" ")
    arguments = argument.split()
    if behaviour in LAYER_BEHAVIOURS:
        return "layer"
    if behaviour in CONTROL_BEHAVIOURS or behaviour.startswith(CONTROL_PREFIXES):
        return "control"
    if behaviour in MODIFIER_BEHAVIOURS and arguments[:1] and arguments[0] in MODIFIER_KEYCODES:
        return "modifier"
    if behaviour.startswith("&dq_"):
        return "morph_key"
    return "key"


def describe_position(layers, layer, position, reveal=False, coordinate=None):
    """Name a position for a reader without disclosing typed content by default.

    Position, matrix coordinate and timing carry the diagnosis. An ordinary key's
    identity does not, and a capture's positions reconstruct typed input once they
    are read against a published keymap.
    """
    row, column = coordinate if coordinate else (None, None)
    binding = binding_at(layers, layer, position)
    binding_class = classify_binding(binding, row)
    described = {"position": position, "binding_class": binding_class}
    if row is not None:
        described.update(row=row, column=column)
    if binding_class in REVEALED_CLASSES or reveal:
        described["binding"] = binding
    return described


def capture_boot(info):
    """Recover the device boot instant so records share a timebase with host logs."""
    if info.get("boot_at"):
        return dt.datetime.fromisoformat(info["boot_at"])
    if info.get("captured_at") and info.get("uptime_ms") is not None:
        captured = dt.datetime.fromisoformat(info["captured_at"])
        return captured - dt.timedelta(milliseconds=info["uptime_ms"])
    return None


def summarise_assertions(assertions):
    """Measure how tightly modifiers arrived, which cadence alone distinguishes.

    Peak count and hold duration read the same for a chord typed over a third of a
    second and for several modifiers appearing inside twenty milliseconds. The
    interval between assertions is what separates them, so it is reported as a
    measurement rather than left to be inferred.
    """
    activity = {
        "assertions": len(assertions),
        "distinct_modifiers": len({item["modifier"] for item in assertions}),
        "shortest_gap_ms": None,
        "tightest_burst": None,
    }
    gaps = [
        item["since_previous_ms"]
        for previous, item in zip(assertions, assertions[1:])
        if item["modifier"] != previous["modifier"]
    ]
    if gaps:
        activity["shortest_gap_ms"] = min(gaps)

    # The widest run of distinct modifiers that arrived without one repeating,
    # taking the shortest such run when several hold the same count.
    best = None
    start = 0
    seen = {}
    for end, item in enumerate(assertions):
        modifier = item["modifier"]
        if modifier in seen and seen[modifier] >= start:
            start = seen[modifier] + 1
        seen[modifier] = end
        candidate = {
            "count": end - start + 1,
            "span_ms": item["uptime_ms"] - assertions[start]["uptime_ms"],
            "modifiers": [entry["modifier"] for entry in assertions[start:end + 1]],
            "at": assertions[start]["at"],
        }
        if best is None or (candidate["count"], -candidate["span_ms"]) > (
            best["count"],
            -best["span_ms"],
        ):
            best = candidate
    activity["tightest_burst"] = best
    return activity


def analyse_capture(objects, layers, reveal=False):
    """Report per-press evidence and what a capture shows at each keyboard layer."""
    info = next((item for item in objects if item.get("kind") == "info"), {})
    records = [item for item in objects if item.get("kind") == "record"]
    boot_at = capture_boot(info)

    def moment(record):
        if record.get("recorded_at"):
            return record["recorded_at"]
        return wall_clock(boot_at, record["uptime_ms"]) if boot_at else None

    def describe(record=None, position=None, layer=None, coordinate=None):
        record = record or {}
        if position is None:
            position = record.get("position")
        if layer is None:
            layer = record.get("default_layer")
        if coordinate is None:
            coordinate = coordinates.get(position)
        return describe_position(layers, layer, position, reveal=reveal, coordinate=coordinate)

    def observe(name, at, **fields):
        observations.append(
            {"observation": name, "layer": OBSERVATIONS[name]["layer"], "at": at, **fields}
        )

    raw_edges = collections.Counter()
    scan_edges = collections.Counter()
    positions = {}
    coordinates = {}
    scanned = set()
    released = set()
    repeats = []
    observations = []
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
            if key[0] != STATE_ROW and key in scanned and key not in released:
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
    state_changes = []
    truncated = []
    pressed_positions = set()
    held = {}
    reports = 0
    default_layer = None
    for index, record in enumerate(records):
        event = record["event"]
        if event == "hid_report":
            reports += 1
        elif event == "modifier":
            if record["error"]:
                observe(
                    "modifier_error",
                    moment(record),
                    modifier=record["modifier"],
                    count=record["count"],
                    report_modifiers=record["report_modifiers"],
                )
        elif event == "kscan_drop":
            observe("kscan_drop", moment(record), **describe(record))
        elif event in ("ppt_queue", "ppt_tx", "hid_send"):
            if record.get("error") or record.get("discarded") or record.get("result", 0) < 0:
                observe(
                    "transport_error",
                    moment(record),
                    stage=event,
                    transport=record.get("transport"),
                    result=record.get("result"),
                    discarded=record.get("discarded"),
                )
        elif event == "keymap":
            default_layer = record["default_layer"]
            position = record["position"]
            if record["pressed"]:
                if position in held:
                    observe("press_without_release", moment(record), **describe(record))
                held[position] = (index, record)
                pressed_positions.add(position)
            elif position not in held:
                if position in pressed_positions or not info.get("overwritten"):
                    observe("release_without_press", moment(record), **describe(record))
                else:
                    truncated.append({"at": moment(record), **describe(record)})
            else:
                start_index, down = held.pop(position)
                key = coordinates.get(position)
                if key and key[0] == STATE_ROW:
                    state_changes.append(
                        {
                            "at": moment(down),
                            "cleared_at": moment(record),
                            **describe(down),
                        }
                    )
                    continue
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
        observe(
            "repeat_without_raw_release",
            moment(record),
            **describe(position=positions.get(key), layer=default_layer, coordinate=key),
        )

    for key, count in sorted(raw_edges.items()):
        if count > scan_edges[key]:
            observe(
                "contact_bounce_absorbed",
                None,
                raw_presses=count,
                debounced_presses=scan_edges[key],
                **describe(position=positions.get(key), layer=default_layer, coordinate=key),
            )

    modifier_state = 0
    modifier_since = {}
    longest_hold = None
    assertions = []
    peak = {"modifiers": 0, "names": [], "at": None}
    for record in records:
        if record["event"] != "hid_report":
            continue
        current = record["modifiers"]
        if bin(current).count("1") > bin(peak["modifiers"]).count("1"):
            peak = {
                "modifiers": current,
                "names": record["modifier_names"],
                "at": moment(record),
            }
        for bit in range(8):
            mask = 1 << bit
            if not (current ^ modifier_state) & mask:
                continue
            if current & mask:
                modifier_since[bit] = record
                assertions.append(
                    {
                        "kind": "modifier_assertion",
                        "modifier": MODIFIERS[bit],
                        "at": moment(record),
                        "uptime_ms": record["uptime_ms"],
                        "since_previous_ms": (
                            record["uptime_ms"] - assertions[-1]["uptime_ms"]
                            if assertions
                            else None
                        ),
                        "report_modifiers": current,
                        "report_modifier_names": record["modifier_names"],
                    }
                )
            else:
                down = modifier_since.pop(bit, None)
                if down is None:
                    continue
                hold = {
                    "modifier": MODIFIERS[bit],
                    "at": moment(down),
                    "held_ms": record["uptime_ms"] - down["uptime_ms"],
                }
                if longest_hold is None or hold["held_ms"] > longest_hold["held_ms"]:
                    longest_hold = hold
        modifier_state = current

    modifier_activity = summarise_assertions(assertions)

    latched = []
    for bit, down in sorted(modifier_since.items()):
        latched.append(
            {
                "modifier": MODIFIERS[bit],
                "at": moment(down),
                "held_ms": records[-1]["uptime_ms"] - down["uptime_ms"],
            }
        )

    device_state = []
    keys_held = []
    for position, (_, down) in sorted(held.items()):
        key = coordinates.get(position)
        if key and key[0] == STATE_ROW:
            device_state.append(binding_at(layers, down["default_layer"], position))
        else:
            keys_held.append(
                {
                    "at": moment(down),
                    "held_ms": records[-1]["uptime_ms"] - down["uptime_ms"],
                    **describe(down),
                }
            )

    summary = {
        "kind": "summary",
        "capture_status": info.get("capture_status", "complete"),
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
        "peak_modifiers": peak,
        "longest_modifier_hold": longest_hold,
        "modifier_activity": modifier_activity,
        "at_freeze": {"modifiers": latched, "keys": keys_held},
        "truncated_releases": truncated,
        "device_state": device_state,
        "device_state_changes": state_changes,
        "keyboard_observations": collections.Counter(
            item["observation"] for item in observations
        ),
        "evidence_boundary": EVIDENCE_BOUNDARY,
        "key_identity": "revealed" if reveal else "classified",
    }
    return {
        "summary": summary,
        "presses": presses,
        "observations": observations,
        "modifier_assertions": assertions,
    }


def run_analyse(args):
    objects = [
        json.loads(line)
        for line in pathlib.Path(args.capture).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    keymap = args.keymap or pathlib.Path(__file__).parents[1] / "config" / KEYMAP_NAME
    layers = keymap_layers(keymap)
    analysis = analyse_capture(objects, layers, reveal=args.reveal_keys)
    summary = analysis["summary"]
    summary["keyboard_observations"] = dict(summary["keyboard_observations"])
    emit(summary, None)
    if args.presses:
        for press in analysis["presses"]:
            emit(press, None)
    for assertion in analysis["modifier_assertions"]:
        emit(assertion, None)
    for observation in analysis["observations"]:
        emit({"kind": "observation", **observation}, None)


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


def validate_capture(objects):
    if not objects:
        raise ValueError("capture is empty")
    header = objects[0]
    if not isinstance(header, dict):
        raise ValueError("capture header is not a JSON object")
    if header.get("kind") != "info":
        raise ValueError("capture does not begin with an info header")
    if not header.get("frozen"):
        raise ValueError("capture header does not describe a frozen ring")
    status = header.get("capture_status", "complete")
    if status != "complete":
        raise ValueError(f"capture is a partial dump: capture_status={status}")

    if any(not isinstance(item, dict) for item in objects[1:]):
        raise ValueError("capture contains a non-object JSONL record")
    unexpected = [
        item.get("kind") for item in objects[1:] if item.get("kind") != "record"
    ]
    if unexpected:
        raise ValueError(f"capture contains unexpected JSONL objects: {unexpected}")
    records = objects[1:]

    protocol_version = header.get("protocol_version", 1)
    if protocol_version not in (1, 2):
        raise ValueError(f"unsupported protocol version: {protocol_version}")
    raw_slots = header.get("raw_slots", header.get("count"))
    if not isinstance(raw_slots, int) or raw_slots < 0:
        raise ValueError("capture header has an invalid raw slot count")
    if header.get("count") != raw_slots:
        raise ValueError("capture header count and raw_slots disagree")

    decoded_records = len(records)
    expected_decoded = header.get("decoded_records")
    expected_time_skip = header.get("time_skip_records")
    method = "header_stats"
    if expected_decoded is None or expected_time_skip is None:
        if protocol_version == 1:
            expected_decoded = raw_slots
            expected_time_skip = 0
            method = "legacy_protocol_1"
        else:
            expected_decoded = decoded_records
            expected_time_skip = raw_slots - decoded_records
            method = "legacy_protocol_2_sequence"

    for name, value in (
        ("decoded_records", expected_decoded),
        ("time_skip_records", expected_time_skip),
    ):
        if not isinstance(value, int) or value < 0:
            raise ValueError(f"capture header has an invalid {name} value")
    if decoded_records != expected_decoded:
        raise ValueError(
            f"decoded record count mismatch: header={expected_decoded}, "
            f"file={decoded_records}"
        )
    if expected_decoded + expected_time_skip != raw_slots:
        raise ValueError(
            "capture accounting mismatch: raw_slots must equal decoded_records "
            "plus time_skip_records"
        )

    next_sequence = header.get("next_sequence_absolute")
    if not isinstance(next_sequence, int):
        raise ValueError("capture header has no absolute next sequence")
    expected_start = next_sequence - raw_slots
    expected_end = next_sequence - 1
    sequences = [record.get("absolute_sequence") for record in records]
    if any(not isinstance(sequence, int) for sequence in sequences):
        raise ValueError("capture contains a record without an absolute sequence")
    if sequences != sorted(sequences) or len(sequences) != len(set(sequences)):
        raise ValueError("capture sequences are duplicate or out of order")
    if any(
        sequence < expected_start or sequence > expected_end
        for sequence in sequences
    ):
        raise ValueError("capture sequence falls outside the firmware ring window")
    missing_slots = raw_slots - len(sequences)
    if missing_slots != expected_time_skip:
        raise ValueError(
            f"sequence coverage mismatch: missing={missing_slots}, "
            f"time_skip_records={expected_time_skip}"
        )

    uptime_unknown = sum(
        1 for record in records if record.get("uptime_unknown")
    )
    expected_unknown = header.get("uptime_unknown_records", uptime_unknown)
    if expected_unknown != uptime_unknown:
        raise ValueError(
            f"unknown uptime count mismatch: header={expected_unknown}, "
            f"file={uptime_unknown}"
        )

    return {
        "kind": "validation",
        "valid": True,
        "method": method,
        "protocol_version": protocol_version,
        "raw_slots": raw_slots,
        "decoded_records": decoded_records,
        "time_skip_records": expected_time_skip,
        "uptime_unknown_records": uptime_unknown,
        "sequence_start": expected_start,
        "sequence_end": expected_end,
    }


def run_validate(args):
    try:
        lines = pathlib.Path(args.capture).read_text(encoding="utf-8").splitlines()
        objects = [json.loads(line) for line in lines if line.strip()]
        result = validate_capture(objects)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(
            json.dumps(
                {
                    "kind": "validation",
                    "valid": False,
                    "error_type": type(error).__name__,
                    "error": str(error),
                },
                sort_keys=True,
            )
        )
        raise SystemExit(1) from error
    print(json.dumps(result, sort_keys=True))


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
        record_size = info["record_size"]
        if record_size not in (RECORD_SIZE, RECORD_SIZE_V2):
            raise RuntimeError(
                f"firmware record size {record_size} does not match decoder "
                f"{RECORD_SIZE} or {RECORD_SIZE_V2}"
            )

        header = {
            "kind": "info",
            "captured_at": after.isoformat(),
            "boot_at": boot_at.isoformat(),
            "boot_uncertainty_ms": (after - before) / dt.timedelta(milliseconds=1),
            **info,
        }
        # A file holds the frozen ring's header from the moment the firmware
        # reports it, so a link that drops mid-read still leaves the freeze
        # reason and ring counts behind.  The final header replaces it.
        rewritable = output is not None and output.seekable()
        if rewritable:
            emit({**header, "capture_status": "partial", "raw_slots": 0}, output)
            output.flush()

        index = 0
        stream = bytearray()
        try:
            while index < info["count"]:
                response = device.exchange("read", index)
                returned = response[3]
                if returned == 0:
                    raise RuntimeError(f"firmware returned no records at index {index}")
                for offset in range(returned):
                    start = 8 + offset * record_size
                    end = start + record_size
                    if end > len(response):
                        raise RuntimeError(
                            f"firmware returned a truncated record at index {index + offset}"
                        )
                    stream += response[start:end]
                index += returned

            expected_bytes = info["count"] * record_size
            if len(stream) != expected_bytes:
                raise RuntimeError(
                    f"raw trace length mismatch: expected={expected_bytes}, "
                    f"received={len(stream)}"
                )
            absolute_sequence = info["next_sequence_absolute"] - info["count"]
            if record_size == RECORD_SIZE_V2:
                records, decode_stats = decode_records_v2(
                    stream,
                    sequence=absolute_sequence,
                    with_stats=True,
                )
            else:
                records = []
                for offset in range(0, len(stream), RECORD_SIZE):
                    record = decode_record(stream[offset:offset + RECORD_SIZE])
                    record["absolute_sequence"] = absolute_sequence + offset // RECORD_SIZE
                    records.append(record)
                decode_stats = {
                    "raw_slots": info["count"],
                    "decoded_records": len(records),
                    "time_skip_records": 0,
                    "uptime_unknown_records": 0,
                }
        except Exception as error:
            if rewritable:
                output.seek(0)
                output.truncate()
                emit(
                    {
                        **header,
                        "capture_status": "partial",
                        "raw_slots": index,
                        "partial_error": str(error),
                        "partial_error_type": type(error).__name__,
                    },
                    output,
                )
                output.flush()
            raise
        if rewritable:
            output.seek(0)
            output.truncate()
        emit({**header, "capture_status": "complete", **decode_stats}, output)
        for record in records:
            if not record.get("uptime_unknown"):
                record["recorded_at"] = wall_clock(boot_at, record["uptime_ms"])
            emit({"kind": "record", **record}, output)
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
    analyse_parser.add_argument(
        "--reveal-keys",
        action="store_true",
        help="render an ordinary key's identity as well as its position",
    )
    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("capture")
    subparsers.add_parser("schema")

    args = parser.parse_args()
    if args.command == "list":
        for index, device in enumerate(candidate_devices(args.vid, args.pid)):
            print(json.dumps(device_summary(index, device), sort_keys=True))
    elif args.command == "serial":
        run_serial(args)
    elif args.command == "analyse":
        run_analyse(args)
    elif args.command == "validate":
        run_validate(args)
    elif args.command == "schema":
        print(json.dumps(capture_schema(), indent=2, sort_keys=True))
    else:
        run_hid_command(args)


if __name__ == "__main__":
    main()
