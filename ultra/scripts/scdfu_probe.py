#!/usr/bin/env python3
"""Read-only sc_dfu probe for the Keychron V6 Ultra (RTL8762G).

Sends ONLY the safe read opcodes (model/version) over the 0x8c HID interface and
prints responses. Never sends START/SEND_BIN/VERIFY/IMAGE_SWITCH, so it cannot
write or switch firmware. Use to confirm the device speaks sc_dfu before any flash.

Talks to /dev/hidraw* directly (the pip `hid` libusb backend cannot claim a kernel
hidraw interface). Find the right node by its report descriptor (usage page 0x8c).
Run after `usbipd attach`; node must be readable (sudo chmod 666 /dev/hidrawN).
"""
import glob, os, sys, time

OUT_ID = 0xb2
READ_OPS = {0x60: "MODEL_INFO", 0x61: "DFU_VERSION", 0x6e: "RTL_PATCH_VERSION"}


def find_node():
    for n in glob.glob("/dev/hidraw*"):
        desc = f"/sys/class/hidraw/{os.path.basename(n)}/device/report_descriptor"
        try:
            if open(desc, "rb").read(2) == b"\x05\x8c":
                return n
        except OSError:
            pass
    return None


def frame(op, sn=1):
    body = [OUT_ID, 0xaa, 0x55, 0x03, (~3) & 0xff, sn, op, op, 0x00]
    return bytes(body + [0] * (33 - len(body)))


def ascii_of(b):
    return "".join(chr(c) if 32 <= c < 127 else "." for c in b)


def main():
    node = find_node()
    if not node:
        print("No 0x8c sc_dfu interface. Attach via usbipd and chmod the node.", file=sys.stderr)
        sys.exit(1)
    fd = os.open(node, os.O_RDWR | os.O_NONBLOCK)
    for op, name in READ_OPS.items():
        os.write(fd, frame(op)); time.sleep(0.2)
        try:
            r = os.read(fd, 33)
        except BlockingIOError:
            r = b""
        print(f"{name}: {r.hex()}  |{ascii_of(r)}|")
    os.close(fd)


if __name__ == "__main__":
    main()
