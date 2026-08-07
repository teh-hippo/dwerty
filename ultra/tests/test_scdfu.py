import importlib.util
import pathlib
import tempfile
import unittest


SCRIPT = pathlib.Path(__file__).parents[1] / "scripts" / "scdfu.py"
SPEC = importlib.util.spec_from_file_location("scdfu", SCRIPT)
scdfu = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scdfu)


def response(sequence, opcode, status=0, data=b""):
    length = len(data) + 6
    frame = bytearray((0xAA, 0x55, length, (~length) & 0xFF, 1, 0xA1))
    frame.extend((sequence, opcode, status))
    frame.extend(data)
    checksum = sum(frame[5:]) & 0xFFFF
    frame.extend(checksum.to_bytes(2, "little"))
    frame.extend(b"\x00" * (scdfu.REPORT_SIZE - len(frame)))
    return scdfu.Response(bytes(frame))


class FakeClient:
    def __init__(self, verify_result=0):
        self.sequence = 3
        self.staged = bytearray()
        self.switched = False
        self.verify_result = verify_result

    def command(self, opcode, data=b"", timeout=1.0, retries=3):
        del timeout, retries
        sequence = self.sequence
        self.sequence = 1 if sequence == 255 else sequence + 1
        if opcode == scdfu.OP_START:
            self.staged.clear()
            return response(sequence, opcode)
        if opcode == scdfu.OP_SEND_BIN:
            self.staged.extend(data)
            crc = scdfu.crc32_rtk(self.staged)
            return response(sequence, opcode, data=b"\x00" + crc.to_bytes(4, "little"))
        if opcode == scdfu.OP_VERIFY:
            crc = scdfu.crc32_rtk(self.staged)
            return response(
                sequence,
                opcode,
                data=bytes((self.verify_result,)) + crc.to_bytes(4, "little"),
            )
        raise AssertionError(f"unexpected opcode {opcode:#x}")

    def send_only(self, opcode, data=b""):
        self.switched = opcode == scdfu.OP_SWITCH and not data


class ScDfuTest(unittest.TestCase):
    def test_default_profile_is_release(self):
        args = scdfu.parser().parse_args(["inspect"])
        self.assertEqual(args.profile, "release")

    def test_crc_matches_reflected_crc_without_final_xor(self):
        self.assertEqual(scdfu.crc32_rtk(b"123456789"), 0x340BC6D9)

    def test_builds_fixed_size_packet(self):
        packet = scdfu.build_packet(scdfu.OP_GET_MODEL, sequence=1)
        self.assertEqual(len(packet), scdfu.REPORT_SIZE)
        self.assertEqual(packet[:8], bytes.fromhex("aa5603fc01606000"))

    def test_parses_matching_response(self):
        report = bytes((scdfu.INPUT_REPORT_ID,)) + response(
            7, scdfu.OP_START, data=b"\x01"
        ).frame
        parsed = scdfu.parse_response(report, 7, scdfu.OP_START)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.status, 0)
        self.assertEqual(parsed.data[0], 1)
        self.assertIsNone(scdfu.parse_response(report, 8, scdfu.OP_START))

    def test_rejects_unprepared_raw_image(self):
        image = bytearray(scdfu.IMAGE_MODEL_OFFSET + len(scdfu.EXPECTED_MODEL))
        image[scdfu.IMAGE_MODEL_OFFSET:] = scdfu.EXPECTED_MODEL
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "zmk.bin"
            path.write_bytes(image)
            with self.assertRaisesRegex(scdfu.ScDfuError, "no prepared Realtek SHA header"):
                scdfu.inspect_image(path)

    def test_accepts_prepared_matching_image(self):
        image = bytearray(scdfu.IMAGE_MODEL_OFFSET + len(scdfu.EXPECTED_MODEL))
        image[scdfu.IMAGE_SHA_OFFSET:scdfu.IMAGE_SHA_OFFSET + scdfu.IMAGE_SHA_SIZE] = (
            bytes(range(1, scdfu.IMAGE_SHA_SIZE + 1))
        )
        image[scdfu.IMAGE_MODEL_OFFSET:] = scdfu.EXPECTED_MODEL
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "zmk_ota.bin"
            path.write_bytes(image)
            info = scdfu.inspect_image(path)
            self.assertEqual(info.model, scdfu.EXPECTED_MODEL)
            self.assertEqual(info.crc32, scdfu.crc32_rtk(image))

    def test_upload_switches_only_after_verify(self):
        client = FakeClient()
        image = bytes(range(47))
        result = scdfu.upload_image(client, image)
        self.assertEqual(bytes(client.staged), image)
        self.assertEqual(result, scdfu.crc32_rtk(image))
        self.assertTrue(client.switched)

    def test_verify_failure_does_not_switch(self):
        client = FakeClient(verify_result=2)
        with self.assertRaisesRegex(scdfu.ScDfuError, "rejected"):
            scdfu.upload_image(client, b"firmware")
        self.assertFalse(client.switched)


if __name__ == "__main__":
    unittest.main()
