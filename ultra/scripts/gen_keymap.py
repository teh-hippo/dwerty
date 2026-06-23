#!/usr/bin/env python3
"""Generate ultra/config/keychron_v6_ultra_ansi.keymap from the stock shield.

We keep the stock keymap's preamble (all of Keychron's custom behaviours,
macros and combos) and regenerate the keymap node into five layers:

    0 DWERTY  - Dvorak keys, with a per-key &mod_morph on every position that
                differs from Qwerty so that holding/one-shotting Ctrl/Alt/GUI
                sends the Qwerty-position key (modifier kept).
    1 QWERTY  - the stock Qwerty base, unchanged.
    2 DVORAK  - plain Dvorak, no morphs.
    3 WIN     - a sparse Mac->Windows overlay held by the Mac/Win slide switch:
                transparent except the function row, the Mac/Win special keys
                and the bottom-row modifier order, so whichever typing layer is
                active (including the DWERTY morphs) shows through.
    4 FN      - the stock Mac fn layer + a &to 0/1/2 layout selector.

The Mac/Win slide switch is a continuously-held GPIO (stock &mo 2). We point it
at the WIN overlay (&mo 3) instead of the old Win base layer, so sliding to
"Win" swaps the modifier order without forcing a different typing layer. FN
sits above WIN (index 4) so the &to layout selectors are never masked.

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


def strip_comments(s):
    s = re.sub(r'/\*.*?\*/', ' ', s, flags=re.S)
    return re.sub(r'//[^\n]*', ' ', s)


def parse_bindings(text):
    """Split a devicetree bindings body into individual behaviour invocations.

    A new binding starts at every &-prefixed token; following non-& tokens are
    that binding's parameters. Comments are stripped first so the positions of
    two layers line up for a position-wise diff.
    """
    out, cur = [], None
    for tok in strip_comments(text).split():
        if tok.startswith('&'):
            if cur is not None:
                out.append(' '.join(cur))
            cur = [tok]
        elif cur is not None:
            cur.append(tok)
    if cur is not None:
        out.append(' '.join(cur))
    return out


def relayer(s):
    """Renumber stock layer references for the new scheme: the fn momentary
    (&mo 1 -> &mo 4) and the Mac/Win slide switch (&mo 2 -> &mo 3, the WIN
    overlay)."""
    return s.replace('&mo 1', '&mo 4').replace('&mo 2', '&mo 3')


def win_overlay(mac_base, win_base):
    """Build the sparse Mac->Windows overlay (layer 3).

    It is &trans at every position except where the stock Mac base and Win base
    differ - the function row, the Mac/Win-specific special keys and the
    bottom-row modifier order - where it takes the stock Win binding. The fn key
    is forced &trans so the active typing layer's fn binding shows through; the
    slide-switch position is already &none in the stock Win base.
    """
    mac = parse_bindings(mac_base)
    win = parse_bindings(win_base)
    assert len(mac) == len(win), (len(mac), len(win))
    fn_pos = mac.index('&mo 1')
    cells = []
    for i, (a, b) in enumerate(zip(mac, win)):
        if i == fn_pos or a == b:
            cells.append('&trans')
        else:
            cells.append(b)
    lines = ['            ' + ' '.join(cells[i:i + 15])
             for i in range(0, len(cells), 15)]
    return '\n'.join(lines), sum(1 for c in cells if c != '&trans')


def main():
    stock = read_stock()
    base = extract_bindings('default_layer', stock)   # Mac base = Qwerty
    macfn = extract_bindings('layer_one', stock)      # Mac fn
    winbase = extract_bindings('layer_two', stock)    # Win base (mods/F-row swap)

    tokens = sorted(DQ.keys(), key=len, reverse=True)
    pat = re.compile(r'&kp\s+(' + '|'.join(tokens) + r')\b')

    dwerty = relayer(pat.sub(lambda m: '&' + bname(m.group(1)), base))
    qwerty = relayer(base)
    dvorak = relayer(pat.sub(lambda m: '&kp ' + DQ[m.group(1)][0], base))

    # FN: stock Mac fn + first three &trans become the layout selector.
    parts = macfn.split('&trans')
    repls = ['&to 0', '&to 1', '&to 2']
    fn = parts[0]
    for k in range(1, len(parts)):
        fn += (repls[k - 1] if k - 1 < len(repls) else '&trans') + parts[k]
    fn = relayer(fn)

    # WIN: sparse Mac->Windows overlay held by the Mac/Win slide switch.
    win, win_keys = win_overlay(base, winbase)

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

    # Replace the stock keymap node (brace-matched) with our five layers.
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

        // Layer 3: WIN  - Mac->Windows overlay held by the Mac/Win slide switch.
        // Transparent except the function row, the Mac/Win special keys and the
        // bottom-row modifier order, so the active typing layer (including the
        // DWERTY morphs) shows through. Slide to "Win" holds &mo 3.
        win_layer {{
            bindings = <
{win}
            >;
            sensor-bindings = <&inc_dec_kp C_VOL_UP C_VOL_DN>;
        }};

        // Layer 4: FN  - RGB/BT/media (from stock) + layout selector (&to 0/1/2)
        fn_layer {{
            bindings = <{fn}>;
            sensor-bindings = <&rgb_encoder>;
        }};
    }};"""

    # combo_a is the stock "fn+j+z" combo, gated on the old fn layers <1 3>.
    # In the new scheme fn is layer 4, so point it there (this also stops it
    # mis-firing on QWERTY, which is layer 1 now).
    head = stock[:start].replace('layers =< 1 3>;', 'layers = <4>;', 1)

    out = head + "\n" + dq_block + "\n    " + new_keymap + stock[end:]
    OUT.write_text(out)
    print(f"wrote {OUT} ({len(out)} bytes); {len(DQ)} morphs, "
          f"{len(re.findall(r'&dq_', dwerty))} dq refs on DWERTY, "
          f"WIN overlay has {win_keys} non-transparent keys")


if __name__ == "__main__":
    main()
