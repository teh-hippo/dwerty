import argparse
import datetime as dt
import importlib.util
import json
import pathlib
import struct
import tempfile
import time
import unittest
from unittest import mock


SCRIPT = pathlib.Path(__file__).parents[1] / "scripts" / "diagnostics.py"
SPEC = importlib.util.spec_from_file_location("diagnostics", SCRIPT)
diagnostics = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(diagnostics)


class FakeHidDevice:
    """A hidapi device that ignores the first `dropped` commands it receives."""

    def __init__(self, dropped):
        self.dropped = dropped
        self.writes = 0
        self._pending = None

    def open_path(self, path):
        self.path = path

    def close(self):
        self._pending = None

    def write(self, report):
        self.writes += 1
        if self.writes > self.dropped:
            response = bytearray(diagnostics.REPORT_SIZE)
            response[0] = diagnostics.COMMAND
            response[1] = report[2]
            self._pending = bytes(response)
        return len(report)

    def read(self, size, timeout_ms):
        if self._pending is None:
            time.sleep(timeout_ms / 1000)
            return b""
        pending, self._pending = self._pending, None
        return pending


def open_fake_device(fake, timeout_ms):
    module = mock.Mock()
    module.device.return_value = fake
    with mock.patch.object(diagnostics, "import_hid", return_value=module):
        return diagnostics.DiagnosticDevice({"path": "fake"}, timeout_ms)


class StaleReadDevice(FakeHidDevice):
    """A device whose first read reply echoes an earlier record index."""

    def __init__(self):
        super().__init__(dropped=0)
        self.replies = []

    def write(self, report):
        self.writes += 1
        requested = struct.unpack_from("<H", bytes(report), 3)[0]
        echoed = 0 if self.writes == 1 else requested
        response = bytearray(diagnostics.REPORT_SIZE)
        response[0] = diagnostics.COMMAND
        response[1] = report[2]
        struct.pack_into("<H", response, 4, echoed)
        self.replies.append(bytes(response))
        return len(report)

    def read(self, size, timeout_ms):
        if not self.replies:
            time.sleep(timeout_ms / 1000)
            return b""
        return self.replies.pop(0)


class DiagnosticsProtocolTest(unittest.TestCase):
    def test_crc16_ccitt_false(self):
        self.assertEqual(diagnostics.crc16(b"123456789"), 0x29B1)

    def test_decodes_matrix_transition(self):
        payload = struct.pack(
            diagnostics.RECORD_FORMAT,
            7,
            3,
            1,
            1234,
            5 | (13 << 8),
            0,
        )
        record = diagnostics.decode_record(payload)
        self.assertEqual(record["event"], "matrix_raw")
        self.assertEqual(record["row"], 5)
        self.assertEqual(record["column"], 13)
        self.assertTrue(record["pressed"])

    def test_decodes_modifier_report(self):
        payload = struct.pack(
            diagnostics.RECORD_FORMAT,
            8,
            10,
            2,
            5678,
            0x0F,
            0xBEEF,
        )
        record = diagnostics.decode_record(payload)
        self.assertEqual(record["transport"], "ppt")
        self.assertEqual(record["modifiers"], 0x0F)
        self.assertEqual(record["modifier_names"], ["lctrl", "lshift", "lalt", "lgui"])

    def test_parses_info_response(self):
        response = bytearray(diagnostics.REPORT_SIZE)
        response[0] = diagnostics.COMMAND
        response[1] = diagnostics.SUBCOMMANDS["info"]
        response[3] = 1
        response[4] = diagnostics.RECORD_SIZE
        struct.pack_into("<H", response, 5, 512)
        struct.pack_into("<H", response, 7, 42)
        struct.pack_into("<H", response, 9, 43)
        response[11] = 1
        response[12] = 2
        struct.pack_into("<I", response, 13, 3)
        struct.pack_into("<I", response, 17, 4)
        struct.pack_into("<I", response, 21, 5000)
        struct.pack_into("<I", response, 27, 65579)
        info = diagnostics.parse_info(bytes(response))
        self.assertEqual(info["capacity"], 512)
        self.assertEqual(info["count"], 42)
        self.assertEqual(info["freeze_reason"], "suspicious_modifiers")
        self.assertEqual(info["uart_dropped"], 4)
        self.assertEqual(info["next_sequence_absolute"], 65579)

    def test_decodes_correlation_mark(self):
        payload = struct.pack(
            diagnostics.RECORD_FORMAT,
            9,
            17,
            0,
            6000,
            0xCDEF,
            0x89AB,
        )
        record = diagnostics.decode_record(payload)
        self.assertEqual(record["event"], "mark")
        self.assertEqual(record["nonce"], 0x89ABCDEF)

    def test_parses_linux_hid_identity(self):
        identity = diagnostics.parse_hid_id("HID_ID=0003:00003434:00000C60\n")
        self.assertEqual(identity, (0x3434, 0x0C60))

    def test_recognises_launcher_report_descriptor(self):
        descriptor = b"\x05\x01" + diagnostics.RAW_DESCRIPTOR_SIGNATURE + b"\xa1\x01"
        self.assertIn(diagnostics.RAW_DESCRIPTOR_SIGNATURE, descriptor)

    def test_missing_optional_hidapi_is_not_required_for_listing(self):
        original_import = __import__

        def import_without_hid(name, *args, **kwargs):
            if name == "hid":
                raise ImportError
            return original_import(name, *args, **kwargs)

        with mock.patch("builtins.__import__", side_effect=import_without_hid):
            self.assertIsNone(diagnostics.import_hid(required=False))

    def test_retransmits_a_command_that_a_settling_link_dropped(self):
        fake = FakeHidDevice(dropped=2)
        device = open_fake_device(fake, 2000)
        with mock.patch.object(diagnostics, "RETRY_INTERVAL_MS", 20):
            response = device.exchange("freeze")
        self.assertEqual(fake.writes, 3)
        self.assertEqual(response[0], diagnostics.COMMAND)
        self.assertEqual(response[1], diagnostics.SUBCOMMANDS["freeze"])

    def test_reports_a_timeout_when_the_device_never_answers(self):
        fake = FakeHidDevice(dropped=100)
        device = open_fake_device(fake, 100)
        with mock.patch.object(diagnostics, "RETRY_INTERVAL_MS", 20):
            with self.assertRaises(RuntimeError):
                device.exchange("info")
        self.assertGreater(fake.writes, 1)

    def test_rejects_a_read_reply_for_another_index(self):
        fake = StaleReadDevice()
        device = open_fake_device(fake, 2000)
        with mock.patch.object(diagnostics, "RETRY_INTERVAL_MS", 20):
            response = device.exchange("read", 4)
        self.assertEqual(fake.writes, 2)
        self.assertEqual(struct.unpack_from("<H", response, 4)[0], 4)


def keymap_event(uptime, position, pressed, layer=3):
    return {
        "kind": "record",
        "event": "keymap",
        "uptime_ms": uptime,
        "position": position,
        "default_layer": layer,
        "pressed": pressed,
    }


def hid_report(uptime):
    return {"kind": "record", "event": "hid_report", "uptime_ms": uptime, "modifiers": 0}


def matrix_event(uptime, row, column, pressed, event="matrix_raw"):
    return {
        "kind": "record",
        "event": event,
        "uptime_ms": uptime,
        "row": row,
        "column": column,
        "pressed": pressed,
    }


def press_sequence(uptime, position, row, column, layer=3):
    return [
        matrix_event(uptime, row, column, True),
        matrix_event(uptime, row, column, True, event="kscan"),
        {
            "kind": "record",
            "event": "position",
            "uptime_ms": uptime,
            "position": position,
            "row": row,
            "column": column,
            "pressed": True,
        },
        keymap_event(uptime, position, True, layer),
        hid_report(uptime),
        matrix_event(uptime + 100, row, column, False),
        matrix_event(uptime + 100, row, column, False, event="kscan"),
        keymap_event(uptime + 100, position, False, layer),
        hid_report(uptime + 100),
    ]


class FakeDumpDevice:
    """A device holding one record, used to check what a dump writes out."""

    def __init__(self, uptime_ms, record_uptime_ms):
        self.uptime_ms = uptime_ms
        self.record_uptime_ms = record_uptime_ms

    def close(self):
        pass

    def exchange(self, subcommand, value=0):
        response = bytearray(diagnostics.REPORT_SIZE)
        response[0] = diagnostics.COMMAND
        response[1] = diagnostics.SUBCOMMANDS[subcommand]
        if subcommand == "read":
            response[3] = 1
            struct.pack_into("<H", response, 4, value)
            response[8:8 + diagnostics.RECORD_SIZE] = struct.pack(
                diagnostics.RECORD_FORMAT, 0, 1, 0, self.record_uptime_ms, 0, 0
            )
            return bytes(response)
        response[3] = 1
        response[4] = diagnostics.RECORD_SIZE
        struct.pack_into("<H", response, 5, 512)
        struct.pack_into("<H", response, 7, 1)
        response[11] = 1
        struct.pack_into("<I", response, 21, self.uptime_ms)
        struct.pack_into("<I", response, 27, 1)
        return bytes(response)


class CaptureAnalysisTest(unittest.TestCase):
    KEYMAP = pathlib.Path(__file__).parents[1] / "config" / diagnostics.KEYMAP_NAME

    def setUp(self):
        self.layers = diagnostics.keymap_layers(self.KEYMAP)

    def test_reads_every_keymap_layer_with_a_uniform_cell_count(self):
        self.assertEqual(
            [layer["name"] for layer in self.layers],
            ["mac_qwerty", "mac_dwerty", "win_qwerty", "win_dwerty", "fn_layer"],
        )
        self.assertEqual({len(layer["bindings"]) for layer in self.layers}, {114})

    def test_names_a_position_from_the_layer_the_firmware_reported(self):
        self.assertEqual(diagnostics.binding_at(self.layers, 3, 95), "&kp LCTRL")
        self.assertEqual(diagnostics.binding_at(self.layers, 3, 63), "&kp A")
        self.assertEqual(diagnostics.binding_at(self.layers, 3, 65), "&dq_d")
        self.assertIsNone(diagnostics.binding_at(self.layers, 3, 4096))

    def test_recovers_the_boot_instant_from_a_capture_without_one(self):
        boot = diagnostics.capture_boot(
            {"captured_at": "2026-08-13T23:04:52.096049+00:00", "uptime_ms": 1761844}
        )
        self.assertEqual(boot.isoformat(), "2026-08-13T22:35:30.252049+00:00")
        self.assertEqual(diagnostics.wall_clock(boot, 1737136), "2026-08-13T23:04:27.388049+00:00")

    def test_a_clean_press_produces_one_report_for_each_edge(self):
        capture = [{"kind": "info", "captured_at": "2026-08-13T23:00:00+00:00", "uptime_ms": 5000}]
        capture += press_sequence(1000, 63, 3, 1)
        summary, presses, anomalies = diagnostics.analyse_capture(capture, self.layers)
        self.assertEqual(summary["presses"], 1)
        self.assertEqual(anomalies, [])
        self.assertEqual(presses[0]["binding"], "&kp A")
        self.assertEqual(presses[0]["press_reports"], 1)
        self.assertEqual(presses[0]["release_reports"], 1)
        self.assertEqual(presses[0]["held_ms"], 100)

    def test_reports_bounce_the_debouncer_absorbed(self):
        capture = press_sequence(1000, 63, 3, 1)
        capture[4:4] = [matrix_event(1002, 3, 1, False), matrix_event(1003, 3, 1, True)]
        _, presses, anomalies = diagnostics.analyse_capture(capture, self.layers)
        self.assertEqual(presses[0]["matrix_edges_while_down"], 3)
        self.assertEqual(
            [(item["anomaly"], item["binding"], item["raw_presses"]) for item in anomalies],
            [("contact_bounce_absorbed", "&kp A", 2)],
        )

    def test_a_second_tap_of_one_key_is_not_a_fault(self):
        capture = press_sequence(1000, 63, 3, 1) + press_sequence(1200, 63, 3, 1)
        summary, _, anomalies = diagnostics.analyse_capture(capture, self.layers)
        self.assertEqual(summary["presses"], 2)
        self.assertEqual(anomalies, [])

    def test_reports_a_repeat_the_switch_never_opened_for(self):
        capture = press_sequence(1000, 63, 3, 1)
        capture[5:5] = [
            matrix_event(1050, 3, 1, True, event="kscan"),
            keymap_event(1050, 63, False),
            hid_report(1050),
            keymap_event(1050, 63, True),
            hid_report(1050),
        ]
        _, _, anomalies = diagnostics.analyse_capture(capture, self.layers)
        self.assertEqual(
            [(item["anomaly"], item["binding"]) for item in anomalies],
            [("repeat_without_raw_release", "&kp A")],
        )

    def test_reports_a_key_still_held_when_the_trace_was_frozen(self):
        capture = [keymap_event(1000, 95, True), hid_report(1000)]
        summary, presses, anomalies = diagnostics.analyse_capture(capture, self.layers)
        self.assertEqual(presses, [])
        self.assertEqual(anomalies[0]["anomaly"], "held_at_freeze")
        self.assertEqual(anomalies[0]["binding"], "&kp LCTRL")
        self.assertIsNone(summary["window_start"])

    def test_reports_a_second_press_that_arrived_without_a_release(self):
        capture = [
            keymap_event(1000, 63, True),
            hid_report(1000),
            keymap_event(1100, 63, True),
            hid_report(1100),
            keymap_event(1200, 63, False),
            hid_report(1200),
        ]
        _, _, anomalies = diagnostics.analyse_capture(capture, self.layers)
        self.assertEqual([item["anomaly"] for item in anomalies], ["press_without_release"])

    def test_reports_a_release_that_never_had_a_press(self):
        capture = [keymap_event(1000, 63, False), hid_report(1000)]
        _, _, anomalies = diagnostics.analyse_capture(capture, self.layers)
        self.assertEqual([item["anomaly"] for item in anomalies], ["release_without_press"])

    def test_a_dump_dates_every_record_against_the_host_clock(self):
        fake = FakeDumpDevice(uptime_ms=60000, record_uptime_ms=20000)
        with tempfile.TemporaryDirectory() as directory:
            capture = pathlib.Path(directory) / "capture.jsonl"
            args = argparse.Namespace(command="dump", output=str(capture))
            with mock.patch.object(diagnostics, "open_selected", return_value=fake):
                diagnostics.run_hid_command(args)
            written = [json.loads(line) for line in capture.read_text().splitlines()]

        header, record = written
        boot = dt.datetime.fromisoformat(header["boot_at"])
        captured = dt.datetime.fromisoformat(header["captured_at"])
        self.assertGreaterEqual(header["boot_uncertainty_ms"], 0)
        self.assertAlmostEqual(
            (captured - boot) / dt.timedelta(milliseconds=1), 60000, delta=1000
        )
        self.assertEqual(
            record["recorded_at"], diagnostics.wall_clock(boot, record["uptime_ms"])
        )
        self.assertEqual(
            diagnostics.capture_boot(header).isoformat(), header["boot_at"]
        )


if __name__ == "__main__":
    unittest.main()
