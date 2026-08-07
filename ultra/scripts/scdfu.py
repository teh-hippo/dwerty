#!/usr/bin/env python3
"""Deploy V6 Ultra firmware through the running firmware's Realtek SC_DFU HID path."""

import argparse
import dataclasses
import glob
import os
import pathlib
import select
import sys
import time


VENDOR_ID = 0x3434
EXPECTED_MODEL = b"KCZKV68K"
DFU_USAGE_PAGE = b"\x05\x8c"
INPUT_REPORT_ID = 0xB1
OUTPUT_REPORT_ID = 0xB2
REPORT_SIZE = 32
CHUNK_SIZE = 16
OTA_TMP_SIZE = 0x59000
IMAGE_SHA_OFFSET = 0x180
IMAGE_SHA_SIZE = 32
IMAGE_MODEL_OFFSET = 0x208

OP_GET_MODEL = 0x60
OP_GET_DFU_VERSION = 0x61
OP_START = 0x63
OP_SEND_BIN = 0x64
OP_VERIFY = 0x65
OP_SWITCH = 0x66
OP_BUILD_INFO = 0x6F

ULTRA_DIR = pathlib.Path(__file__).resolve().parents[1]
PROFILE_IMAGES = {
    "release": ULTRA_DIR / "build" / "zmk_ota.bin",
    "diagnostics": ULTRA_DIR / "build" / "diagnostics" / "zmk_ota.bin",
    "diagnostics-uart": ULTRA_DIR / "build" / "diagnostics-uart" / "zmk_ota.bin",
}


class ScDfuError(RuntimeError):
    pass


@dataclasses.dataclass(frozen=True)
class Response:
    frame: bytes

    @property
    def status(self):
        return self.frame[8]

    @property
    def data(self):
        return self.frame[9:]


@dataclasses.dataclass(frozen=True)
class DeviceInfo:
    model: bytes
    firmware: str
    build: str
    dfu_version: int
    encryption: int


@dataclasses.dataclass(frozen=True)
class ImageInfo:
    path: pathlib.Path
    data: bytes
    model: bytes
    crc32: int


def crc32_rtk(data, crc=0xFFFFFFFF):
    for value in data:
        current = (crc ^ value) & 0xFF
        for _ in range(8):
            current = (current >> 1) ^ 0xEDB88320 if current & 1 else current >> 1
        crc = (crc >> 8) ^ current
    return crc & 0xFFFFFFFF


def build_packet(opcode, data=b"", sequence=1):
    length = len(data) + 3
    frame = bytearray((0xAA, 0x56, length, (~length) & 0xFF, sequence, opcode))
    frame.extend(data)
    checksum = (opcode + sum(data)) & 0xFFFF
    frame.extend(checksum.to_bytes(2, "little"))
    if len(frame) > REPORT_SIZE:
        raise ValueError(f"SC_DFU frame is too large: {len(frame)} bytes")
    frame.extend(b"\x00" * (REPORT_SIZE - len(frame)))
    return bytes(frame)


def parse_response(report, sequence, opcode):
    if len(report) == REPORT_SIZE + 1 and report[0] == INPUT_REPORT_ID:
        frame = report[1:]
    elif len(report) == REPORT_SIZE:
        frame = report
    else:
        return None
    if frame[:2] != b"\xAA\x55":
        return None
    if frame[2] != ((~frame[3]) & 0xFF):
        return None
    if frame[6] != sequence or frame[7] != opcode:
        return None

    declared_length = frame[2]
    frame_end = 5 + declared_length
    if frame_end <= len(frame):
        checksum_offset = frame_end - 2
        expected = int.from_bytes(frame[checksum_offset:frame_end], "little")
        actual = sum(frame[5:checksum_offset]) & 0xFFFF
        if expected != actual:
            return None
    return Response(frame)


def inspect_image(path):
    path = pathlib.Path(path).resolve()
    try:
        data = path.read_bytes()
    except OSError as error:
        raise ScDfuError(f"cannot read firmware image {path}: {error}") from error
    if len(data) > OTA_TMP_SIZE:
        raise ScDfuError(
            f"image is {len(data)} bytes, exceeding the 0x{OTA_TMP_SIZE:x}-byte OTA staging bank"
        )
    if len(data) < IMAGE_MODEL_OFFSET + len(EXPECTED_MODEL):
        raise ScDfuError("image is too small to contain a Realtek application header")

    sha = data[IMAGE_SHA_OFFSET:IMAGE_SHA_OFFSET + IMAGE_SHA_SIZE]
    if not sha or all(value == 0 for value in sha) or all(value == 0xFF for value in sha):
        raise ScDfuError(
            "image has no prepared Realtek SHA header; use zmk_ota.bin from package.sh, "
            "not raw zmk.bin"
        )
    model = data[IMAGE_MODEL_OFFSET:IMAGE_MODEL_OFFSET + len(EXPECTED_MODEL)]
    if model != EXPECTED_MODEL:
        raise ScDfuError(
            f"image model is {model!r}, expected {EXPECTED_MODEL!r}; refusing cross-model flash"
        )
    return ImageInfo(path=path, data=data, model=model, crc32=crc32_rtk(data))


def _hidraw_sys_path(node):
    return pathlib.Path("/sys/class/hidraw") / pathlib.Path(node).name / "device"


def _is_keychron_node(node):
    try:
        uevent = (_hidraw_sys_path(node) / "uevent").read_text().upper()
    except OSError:
        return False
    return f":0000{VENDOR_ID:04X}:" in uevent


def find_dfu_nodes():
    found = []
    for node in sorted(glob.glob("/dev/hidraw*")):
        try:
            descriptor = (_hidraw_sys_path(node) / "report_descriptor").read_bytes()
        except OSError:
            continue
        if _is_keychron_node(node) and DFU_USAGE_PAGE in descriptor:
            found.append(node)
    return found


def processes_holding(nodes):
    node_set = set(nodes)
    holders = []
    for fd_dir in glob.glob("/proc/[0-9]*/fd"):
        try:
            pid = int(fd_dir.split("/")[2])
        except (IndexError, ValueError):
            continue
        if pid == os.getpid():
            continue
        try:
            descriptors = os.listdir(fd_dir)
        except OSError:
            continue
        for descriptor in descriptors:
            try:
                target = os.readlink(os.path.join(fd_dir, descriptor))
            except OSError:
                continue
            if target not in node_set:
                continue
            try:
                command = pathlib.Path(f"/proc/{pid}/comm").read_text().strip()
            except OSError:
                command = "?"
            holders.append((pid, command, target))
    return sorted(set(holders))


class HidrawTransport:
    def __init__(self, node):
        try:
            self.fd = os.open(node, os.O_RDWR | os.O_NONBLOCK)
        except PermissionError as error:
            raise ScDfuError(
                f"permission denied opening {node}; run with sudo or install a hidraw udev rule"
            ) from error
        except OSError as error:
            raise ScDfuError(f"cannot open {node}: {error}") from error
        self.node = node
        self.drain()

    def close(self):
        os.close(self.fd)

    def drain(self):
        while True:
            readable, _, _ = select.select((self.fd,), (), (), 0)
            if not readable:
                return
            os.read(self.fd, 64)

    def send(self, frame):
        report = bytes((OUTPUT_REPORT_ID,)) + frame
        written = os.write(self.fd, report)
        if written != len(report):
            raise ScDfuError(f"short HID write: {written}/{len(report)} bytes")

    def receive(self, timeout):
        readable, _, _ = select.select((self.fd,), (), (), timeout)
        if not readable:
            return None
        return os.read(self.fd, REPORT_SIZE + 1)


class ScDfuClient:
    def __init__(self, transport):
        self.transport = transport
        self.next_sequence = 1

    def _sequence(self):
        sequence = self.next_sequence
        self.next_sequence = 1 if sequence == 255 else sequence + 1
        return sequence

    def command(self, opcode, data=b"", timeout=1.0, retries=3):
        sequence = self._sequence()
        frame = build_packet(opcode, data, sequence)
        for _ in range(retries):
            self.transport.send(frame)
            deadline = time.monotonic() + timeout
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                report = self.transport.receive(remaining)
                if report is None:
                    break
                response = parse_response(report, sequence, opcode)
                if response is not None:
                    return response
        raise ScDfuError(
            f"no matching acknowledgement for opcode 0x{opcode:02x}, sequence {sequence}"
        )

    def send_only(self, opcode, data=b""):
        sequence = self._sequence()
        self.transport.send(build_packet(opcode, data, sequence))


def _text(data):
    return data.split(b"\x00", 1)[0].decode("ascii", errors="replace").strip()


def probe_device(client):
    model_response = client.command(OP_GET_MODEL)
    if model_response.status:
        raise ScDfuError(f"GET_MODEL_INFO failed with status {model_response.status}")
    model = bytes(model_response.data[:10]).split(b"\x00", 1)[0]
    firmware = _text(model_response.data[12:22])

    version_response = client.command(OP_GET_DFU_VERSION)
    if version_response.status or len(version_response.data) < 3:
        raise ScDfuError("GET_DFU_VERSION returned an invalid response")
    dfu_version = int.from_bytes(version_response.data[:2], "little")
    encryption = version_response.data[2]

    build = ""
    try:
        build_response = client.command(OP_BUILD_INFO)
        if not build_response.status:
            build = _text(build_response.data)
    except ScDfuError:
        pass
    return DeviceInfo(
        model=model,
        firmware=firmware,
        build=build,
        dfu_version=dfu_version,
        encryption=encryption,
    )


def upload_image(client, image, progress=None, retries=3):
    start = client.command(OP_START, b"\x00", retries=retries)
    if start.status:
        raise ScDfuError(f"START was rejected with status {start.status}")

    running_crc = 0xFFFFFFFF
    total = (len(image) + CHUNK_SIZE - 1) // CHUNK_SIZE
    for index, offset in enumerate(range(0, len(image), CHUNK_SIZE), start=1):
        chunk = image[offset:offset + CHUNK_SIZE]
        response = client.command(OP_SEND_BIN, chunk, retries=retries)
        if response.status:
            raise ScDfuError(
                f"chunk {index}/{total} was rejected with status {response.status}"
            )
        if len(response.data) < 5:
            raise ScDfuError(f"chunk {index}/{total} returned a truncated CRC acknowledgement")
        running_crc = crc32_rtk(chunk, running_crc)
        device_crc = int.from_bytes(response.data[1:5], "little")
        if device_crc != running_crc:
            raise ScDfuError(
                f"chunk {index}/{total} diverged: device CRC 0x{device_crc:08x}, "
                f"expected 0x{running_crc:08x}"
            )
        if progress:
            progress(index, total)

    final_crc = crc32_rtk(image)
    verify_data = final_crc.to_bytes(4, "little") * 2
    verify = client.command(OP_VERIFY, verify_data, timeout=3.0, retries=retries)
    if verify.status:
        raise ScDfuError(f"VERIFY transport status was {verify.status}")
    if not verify.data or verify.data[0] != 0:
        result = verify.data[0] if verify.data else "missing"
        raise ScDfuError(f"device rejected the staged image during VERIFY ({result})")
    if len(verify.data) >= 5:
        device_crc = int.from_bytes(verify.data[1:5], "little")
        if device_crc != final_crc:
            raise ScDfuError(
                f"VERIFY returned CRC 0x{device_crc:08x}, expected 0x{final_crc:08x}"
            )
    client.send_only(OP_SWITCH)
    return final_crc


def choose_node(requested=None):
    found = find_dfu_nodes()
    if requested:
        if requested not in found:
            raise ScDfuError(
                f"{requested} is not a Keychron SC_DFU interface; found {found or 'none'}"
            )
        return requested
    if not found:
        raise ScDfuError(
            "no Keychron SC_DFU HID interface found; connect the keyboard by USB and, "
            "under WSL, attach it with usbipd"
        )
    if len(found) > 1:
        raise ScDfuError(
            f"multiple Keychron SC_DFU interfaces found: {', '.join(found)}; use --device"
        )
    return found[0]


def open_client(node):
    transport = HidrawTransport(node)
    return transport, ScDfuClient(transport)


def print_device(info):
    print(f"model:        {info.model.decode(errors='replace')}")
    print(f"firmware:     {info.firmware or 'unknown'}")
    print(f"build:        {info.build or 'unknown'}")
    print(f"DFU version:  {info.dfu_version}")
    print(f"encryption:   {info.encryption}")


def confirm_flash(info, image, assume_yes):
    print_device(info)
    print(f"image:        {image.path}")
    print(f"image bytes:  {len(image.data)}")
    print(f"image CRC32:  0x{image.crc32:08x}")
    if assume_yes:
        return
    if not sys.stdin.isatty():
        raise ScDfuError("interactive confirmation is unavailable; pass --yes explicitly")
    answer = input(f"Type {EXPECTED_MODEL.decode()} to stage, verify and activate this image: ")
    if answer.strip() != EXPECTED_MODEL.decode():
        raise ScDfuError("confirmation did not match; no firmware was written")


def progress_printer(index, total):
    if index == total or index == 1 or index % max(1, total // 20) == 0:
        print(f"\ruploading: {index}/{total} chunks ({index * 100 // total}%)", end="", flush=True)
        if index == total:
            print()


def resolve_image(args):
    if args.image:
        return inspect_image(args.image)
    return inspect_image(PROFILE_IMAGES[args.profile])


def run_probe(args):
    node = choose_node(args.device)
    transport, client = open_client(node)
    try:
        print(f"SC_DFU interface: {node}")
        info = probe_device(client)
        print_device(info)
        if info.model != EXPECTED_MODEL:
            raise ScDfuError(
                f"connected model {info.model!r} is not this repository's {EXPECTED_MODEL!r}"
            )
    finally:
        transport.close()


def run_inspect(args):
    image = resolve_image(args)
    print(f"image:       {image.path}")
    print(f"model:       {image.model.decode()}")
    print(f"bytes:       {len(image.data)}")
    print(f"CRC32:       0x{image.crc32:08x}")
    print("Realtek SHA: present")


def run_flash(args):
    image = resolve_image(args)
    all_keychron_nodes = [node for node in glob.glob("/dev/hidraw*") if _is_keychron_node(node)]
    holders = processes_holding(all_keychron_nodes)
    if holders and not args.force:
        lines = ", ".join(f"{command}({pid}) on {node}" for pid, command, node in holders)
        raise ScDfuError(
            f"another process has the keyboard open: {lines}. Stop it or pass --force."
        )

    node = choose_node(args.device)
    transport, client = open_client(node)
    try:
        print(f"SC_DFU interface: {node}")
        info = probe_device(client)
        if info.model != EXPECTED_MODEL:
            raise ScDfuError(
                f"connected model {info.model!r} is not this repository's {EXPECTED_MODEL!r}"
            )
        if image.model != info.model:
            raise ScDfuError(
                f"image model {image.model!r} does not match device model {info.model!r}"
            )
        if info.dfu_version != 1 or info.encryption != 0:
            raise ScDfuError(
                f"unsupported SC_DFU capabilities: version={info.dfu_version}, "
                f"encryption={info.encryption}"
            )
        confirm_flash(info, image, args.yes)
        print("staging image; the current firmware remains active until verification succeeds")
        crc = upload_image(
            client, image.data, progress=progress_printer, retries=args.retries
        )
        print(f"verified CRC32 0x{crc:08x}; image switch sent")
    finally:
        transport.close()
    print("The keyboard should reboot. Re-run `scdfu.py probe` after it reconnects.")


def parser():
    common_image = argparse.ArgumentParser(add_help=False)
    source = common_image.add_mutually_exclusive_group()
    source.add_argument("--image", type=pathlib.Path)
    source.add_argument(
        "--profile",
        choices=tuple(PROFILE_IMAGES),
        default="diagnostics",
        help="packaged build profile to use when --image is omitted",
    )

    root = argparse.ArgumentParser()
    commands = root.add_subparsers(dest="command", required=True)

    probe = commands.add_parser("probe", help="read-only device identification")
    probe.add_argument("--device")
    probe.set_defaults(handler=run_probe)

    inspect = commands.add_parser(
        "inspect", parents=(common_image,), help="validate an image without a device"
    )
    inspect.set_defaults(handler=run_inspect)

    flash = commands.add_parser(
        "flash", parents=(common_image,), help="stage, verify and activate an image"
    )
    flash.add_argument("--device")
    flash.add_argument("--yes", action="store_true", help="skip the typed model confirmation")
    flash.add_argument(
        "--force", action="store_true", help="ignore other processes holding Keychron HID nodes"
    )
    flash.add_argument("--retries", type=int, default=3)
    flash.set_defaults(handler=run_flash)
    return root


def main(argv=None):
    args = parser().parse_args(argv)
    if getattr(args, "retries", 1) < 1:
        raise SystemExit("--retries must be at least 1")
    try:
        args.handler(args)
    except ScDfuError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
