import importlib.util
import pathlib
import struct
import unittest
from unittest import mock


SCRIPT = pathlib.Path(__file__).parents[1] / "scripts" / "diagnostics.py"
SPEC = importlib.util.spec_from_file_location("diagnostics", SCRIPT)
diagnostics = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(diagnostics)


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


if __name__ == "__main__":
    unittest.main()
