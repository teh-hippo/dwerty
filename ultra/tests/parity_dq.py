#!/usr/bin/env python3
"""Cross-firmware parity: the V6 Ultra Dvorak->Qwerty shortcut pairs must match
the V6 Max keymap exactly. max/ is the source of truth (qwerty_shortcut_map[]);
ultra/ encodes the same pairs in gen_keymap.py's DQ using ZMK key tokens. This
asserts they stay identical so the two firmwares never drift.

Run: python3 ultra/tests/parity_dq.py
"""
import re
import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
MAX_KEYMAP = ROOT / "max" / "keymaps" / "keychron" / "v6_max" / "ansi_encoder" / \
    "keymaps" / "dvorak_qwerty" / "keymap.c"
sys.path.insert(0, str(ROOT / "ultra" / "scripts"))
from gen_keymap import DQ  # noqa: E402

# QMK KC_* token -> ZMK token, only where they differ.
QMK_TO_ZMK = {
    "QUOT": "SQT", "COMM": "COMMA", "SLSH": "FSLH", "EQL": "EQUAL",
    "MINS": "MINUS", "SCLN": "SEMI", "LBRC": "LBKT", "RBRC": "RBKT",
}


def zmk(tok):
    return QMK_TO_ZMK.get(tok, tok)


def parse_max():
    text = MAX_KEYMAP.read_text()
    body = text[text.index("qwerty_shortcut_map[]"):]
    pairs = re.findall(r"\{KC_(\w+),\s*KC_(\w+)\}", body)
    return {zmk(dv): zmk(qw) for dv, qw in pairs}


def main():
    max_pairs = parse_max()
    ultra_pairs = {dv: qw for _, (dv, qw) in DQ.items()}
    if max_pairs != ultra_pairs:
        only_max = set(max_pairs.items()) - set(ultra_pairs.items())
        only_ultra = set(ultra_pairs.items()) - set(max_pairs.items())
        print("DQ parity FAILED")
        print("  only in max:  ", sorted(only_max))
        print("  only in ultra:", sorted(only_ultra))
        sys.exit(1)
    print(f"DQ parity OK: {len(max_pairs)} Dvorak->Qwerty pairs match max")


if __name__ == "__main__":
    main()
