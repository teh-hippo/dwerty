#!/usr/bin/env python3
"""Generate ultra/config/keychron_v6_ultra_ansi.keymap from the stock shield.

We keep the stock keymap's preamble (all of Keychron's custom behaviours,
macros and combos) and regenerate the keymap node into four layers:

    0 DWERTY  - Dvorak keys, with a per-key &mod_morph on every position that
                differs from Qwerty so that holding/one-shotting Ctrl/Alt/GUI
                sends the Qwerty-position key (modifier kept).
    1 QWERTY  - the stock Qwerty base, unchanged.
    2 DVORAK  - plain Dvorak, no morphs.
    3 FN      - the stock Mac fn layer + a &to 0/1/2 layout selector.

The stock keymap is read from git (HEAD) in the fork workspace so it is always
pristine, even after build.sh has copied our keymap over the working file.

Usage: python3 ultra/scripts/gen_keymap.py
"""
import re
import subprocess
import pathlib

ULTRA = pathlib.Path(__file__).resolve().parents[1]
FORK_ZMK = ULTRA / ".cache" / "fork" / "zmk"
REL = "app/boards/shields/keychron_v6_ultra_ansi/keychron_v6_ultra_ansi.keymap"
OUT = ULTRA / "config" / "keychron_v6_ultra_ansi.keymap"

# (physical Qwerty token) -> (Dvorak token, Qwerty token). A and M are identical
# between the layouts, so they stay plain &kp and get no morph.
DQ = {
    'Q': ('SQT', 'Q'), 'W': ('COMMA', 'W'), 'E': ('DOT', 'E'), 'R': ('P', 'R'),
    'T': ('Y', 'T'), 'Y': ('F', 'Y'), 'U': ('G', 'U'), 'I': ('C', 'I'),
    'O': ('R', 'O'), 'P': ('L', 'P'), 'LBKT': ('FSLH', 'LBKT'), 'RBKT': ('EQUAL', 'RBKT'),
    'S': ('O', 'S'), 'D': ('E', 'D'), 'F': ('U', 'F'), 'G': ('I', 'G'), 'H': ('D', 'H'),
    'J': ('H', 'J'), 'K': ('T', 'K'), 'L': ('N', 'L'), 'SEMI': ('S', 'SEMI'), 'SQT': ('MINUS', 'SQT'),
    'Z': ('SEMI', 'Z'), 'X': ('Q', 'X'), 'C': ('J', 'C'), 'V': ('K', 'V'), 'B': ('X', 'B'),
    'N': ('B', 'N'), 'COMMA': ('W', 'COMMA'), 'DOT': ('V', 'DOT'), 'FSLH': ('Z', 'FSLH'),
    'MINUS': ('LBKT', 'MINUS'), 'EQUAL': ('RBKT', 'EQUAL'),
}


def bname(q):
    return 'dq_' + q.lower()


def read_stock():
    return subprocess.check_output(
        ['git', '-C', str(FORK_ZMK), 'show', f'HEAD:{REL}'], text=True)


def extract_bindings(block_name, text):
    m = re.search(block_name + r'\s*\{', text)
    i = m.end()
    b = text.find('bindings', i)
    lt = text.find('<', b)
    gt = text.find('>;', lt)
    return text[lt + 1:gt]


def main():
    stock = read_stock()
    base = extract_bindings('default_layer', stock)   # Mac base = Qwerty
    macfn = extract_bindings('layer_one', stock)      # Mac fn

    tokens = sorted(DQ.keys(), key=len, reverse=True)
    pat = re.compile(r'&kp\s+(' + '|'.join(tokens) + r')\b')

    dwerty = pat.sub(lambda m: '&' + bname(m.group(1)), base).replace('&mo 1', '&mo 3')
    qwerty = base.replace('&mo 1', '&mo 3')
    dvorak = pat.sub(lambda m: '&kp ' + DQ[m.group(1)][0], base).replace('&mo 1', '&mo 3')

    # FN: stock Mac fn + first three &trans become the layout selector.
    parts = macfn.split('&trans')
    repls = ['&to 0', '&to 1', '&to 2']
    fn = parts[0]
    for k in range(1, len(parts)):
        fn += (repls[k - 1] if k - 1 < len(repls) else '&trans') + parts[k]

    dq_defs = []
    for q, (dv, qw) in DQ.items():
        dq_defs.append(
            f"        {bname(q)}: {bname(q)} {{\n"
            f"            compatible = \"zmk,behavior-mod-morph\";\n"
            f"            #binding-cells = <0>;\n"
            f"            bindings = <&kp {dv}>, <&kp {qw}>;\n"
            f"            mods = <(MOD_LCTL|MOD_RCTL|MOD_LALT|MOD_RALT|MOD_LGUI|MOD_RGUI)>;\n"
            f"            keep-mods = <(MOD_LCTL|MOD_RCTL|MOD_LALT|MOD_RALT|MOD_LGUI|MOD_RGUI)>;\n"
            f"        }};")
    dq_block = "    behaviors {\n" + "\n".join(dq_defs) + "\n    };\n"

    # Replace the stock keymap node (brace-matched) with our four layers.
    km = re.search(r'\n\s*keymap\s*\{', stock)
    start = km.start()
    bo = stock.index('{', km.start())
    depth, j = 0, bo
    while j < len(stock):
        if stock[j] == '{':
            depth += 1
        elif stock[j] == '}':
            depth -= 1
            if depth == 0:
                break
        j += 1
    end = stock.index(';', j) + 1

    new_keymap = f"""keymap {{
        compatible = "zmk,keymap";

        // Layer 0: DWERTY  - Dvorak keys + Qwerty-position shortcut morphs
        dwerty_layer {{
            bindings = <{dwerty}>;
            sensor-bindings = <&inc_dec_kp C_VOL_UP C_VOL_DN>;
        }};

        // Layer 1: QWERTY  - plain Qwerty
        qwerty_layer {{
            bindings = <{qwerty}>;
            sensor-bindings = <&inc_dec_kp C_VOL_UP C_VOL_DN>;
        }};

        // Layer 2: DVORAK  - plain Dvorak, no shortcut morphs
        dvorak_layer {{
            bindings = <{dvorak}>;
            sensor-bindings = <&inc_dec_kp C_VOL_UP C_VOL_DN>;
        }};

        // Layer 3: FN  - RGB/BT/media (from stock) + layout selector (&to 0/1/2)
        fn_layer {{
            bindings = <{fn}>;
            sensor-bindings = <&rgb_encoder>;
        }};
    }};"""

    out = stock[:start] + "\n" + dq_block + "\n    " + new_keymap + stock[end:]
    OUT.write_text(out)
    print(f"wrote {OUT} ({len(out)} bytes); {len(DQ)} morphs, "
          f"{len(re.findall(r'&dq_', dwerty))} dq refs on DWERTY")


if __name__ == "__main__":
    main()
