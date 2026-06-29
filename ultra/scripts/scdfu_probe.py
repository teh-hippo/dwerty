#!/usr/bin/env python3
"""Read-only sc_dfu probe for the Keychron V6 Ultra (RTL8762G).

Sends ONLY the safe read opcodes (model/version) over the 0x8c HID interface and
prints responses. Never sends START/SEND_BIN/VERIFY/IMAGE_SWITCH, so it cannot
write or switch firmware. Use to confirm the device speaks sc_dfu before any flash.

Run after `usbipd attach` so /dev/hidraw* exists. Needs: pip install hidapi.
"""
import sys, hid

VID, PID = 0x3434, 0x0c60
OUT_ID, IN_ID = 0xb2, 0xb1
READ_OPS = {0x60: "MODEL_INFO", 0x61: "DFU_VERSION", 0x6e: "RTL_PATCH_VERSION"}


def frame(op, sn=1):
    body = [0xaa, 0x55, 0x03, (~3) & 0xff, sn, op, op, 0x00]
    return [OUT_ID] + body + [0] * (64 - len(body))


def main():
    devs = [d for d in hid.enumerate(VID, PID)]
    if not devs:
        print("No 3434:0c60 HID device. Attach via usbipd first.", file=sys.stderr); sys.exit(1)
    h = hid.device(); h.open(VID, PID); h.set_nonblocking(1)
    for op, name in READ_OPS.items():
        h.write(frame(op))
        import time; time.sleep(0.2)
        print(f"{name}: {h.read(64)}")
    h.close()


if __name__ == "__main__":
    main()
