#!/usr/bin/env python3
"""Generate ultra/config/keychron_v6_ultra_ansi.keymap from the stock shield.

We keep the stock keymap's preamble (all of Keychron's custom behaviours,
macros and combos) and regenerate the keymap node into five layers, mirroring
the QMK max/ firmware (which dropped pure Dvorak):

    0 MAC_QWERTY - stock Mac base, unchanged.
    1 MAC_DWERTY - Mac base, Dvorak letters with a per-key &mod_morph on every
                   position that differs from Qwerty so holding/one-shotting
                   Ctrl/Alt/GUI sends the Qwerty-position key (modifier kept).
    2 WIN_QWERTY - stock Win base, unchanged.
    3 WIN_DWERTY - Win base + the same Dvorak/morphs.
    4 FN         - stock Mac fn (RGB/BT/media); shared by both halves.

Mac/Win is the native Keychron slide switch (a maintained GPIO). Rather than the
stock momentary &mo overlay - which a marginal boot scan can miss, leaving the
board stuck on Mac - our keymap.c patch reads the slide GPIO level and drives the
OS-half bit of the default layer at boot and on every edge, so the slide is
honoured deterministically. The slide cell (position 109) is therefore &none
here. The fn key becomes &mo 4 on every base. Fn+Z is bound to `&to 0xFF`, a
sentinel our patch turns into "flip the Dvorak/Qwerty mode bit" (0<->1, 2<->3);
only that mode bit is persisted, so the slide always wins at boot and the typing
choice survives reboot.

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
# between the layouts, so they stay plain &kp and get no morph. This MUST stay
# identical to max's qwerty_shortcut_map[] (see max/.../keymap.c).
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


def morph(base):
    """Replace each differing &kp with its &dq_* mod-morph (Dvorak typing)."""
    tokens = sorted(DQ.keys(), key=len, reverse=True)
    pat = re.compile(r'&kp\s+(' + '|'.join(tokens) + r')\b')
    return pat.sub(lambda m: '&' + bname(m.group(1)), base)


def split_cells(b):
    """Split a bindings body into per-position cells (a cell is a &behaviour
    plus its params), so a cell can be replaced by key position."""
    cells, cur = [], None
    for t in b.split():
        if t.startswith('&'):
            if cur:
                cells.append(' '.join(cur))
            cur = [t]
        elif cur:
            cur.append(t)
    if cur:
        cells.append(' '.join(cur))
    return cells


def set_cell(b, pos, val):
    cells = split_cells(b)
    cells[pos] = val
    return ' '.join(cells)


def main():
    stock = read_stock()
    macbase = extract_bindings('default_layer', stock)  # Mac base = Qwerty
    macfn = extract_bindings('layer_one', stock)        # Mac fn
    winbase = extract_bindings('layer_two', stock)      # Win base (mods/F-row)

    # fn -> &mo 4 on every base. The Mac/Win slide (position 109) is driven in C:
    # our keymap.c patch reads the slide GPIO level and sets the OS-half bit of
    # the default layer at boot and on every edge, so the switch is honoured
    # deterministically (the stock momentary &mo overlay could be missed by a
    # marginal boot scan, leaving the board stuck on Mac). Neutralise the stock
    # slide overlay (&mo 2) to &none on the Mac bases; the Win bases are &none
    # already. A targeted replace keeps the stock multi-line layout intact.
    mac_qwerty = macbase.replace('&mo 1', '&mo 4').replace('&mo 2', '&none')
    mac_dwerty = morph(macbase).replace('&mo 1', '&mo 4').replace('&mo 2', '&none')
    win_qwerty = winbase.replace('&mo 3', '&mo 4')
    win_dwerty = morph(winbase).replace('&mo 3', '&mo 4')
    # Fn+Z: Z (position 80) on the FN layer becomes &to 0xFF, a sentinel our
    # keymap.c patch turns into a persisted Dwerty<->Qwerty toggle (mode bit only).
    fn = set_cell(re.sub(r'//[^\n]*', '', macfn).replace('&mo 1', '&mo 4'), 80, '&to 0xFF')

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

        // Layer 0: MAC_QWERTY - stock Mac base
        mac_qwerty {{
            bindings = <{mac_qwerty}>;
            sensor-bindings = <&inc_dec_kp C_VOL_UP C_VOL_DN>;
        }};

        // Layer 1: MAC_DWERTY - Mac Dvorak + Qwerty-position shortcut morphs
        mac_dwerty {{
            bindings = <{mac_dwerty}>;
            sensor-bindings = <&inc_dec_kp C_VOL_UP C_VOL_DN>;
        }};

        // Layer 2: WIN_QWERTY - stock Win base
        win_qwerty {{
            bindings = <{win_qwerty}>;
            sensor-bindings = <&inc_dec_kp C_VOL_UP C_VOL_DN>;
        }};

        // Layer 3: WIN_DWERTY - Win Dvorak + Qwerty-position shortcut morphs
        win_dwerty {{
            bindings = <{win_dwerty}>;
            sensor-bindings = <&inc_dec_kp C_VOL_UP C_VOL_DN>;
        }};

        // Layer 4: FN - stock RGB/BT/media overlay, shared by both OS halves
        fn_layer {{
            bindings = <{fn}>;
            sensor-bindings = <&rgb_encoder>;
        }};
    }};"""

    # combo_a was stock "fn+j+z" on layers <1 3>. Repurpose it as our Fn+Z
    # Dwerty<->Qwerty toggle: Z (pos 80) on the FN layer (4), &to 0xFF, which
    # our keymap.c patch turns into a persisted half-toggle (0<->1, 2<->3).
    # Leave the stock combo intact but re-point it to the FN layer so it can't
    # misfire on a base layer; Fn+Z lives on the FN layer (above) instead.
    head = stock[:start]
    head = head.replace('layers =< 1 3>;', 'layers = <4>;', 1)

    out = head + "\n" + dq_block + "\n    " + new_keymap + stock[end:]
    OUT.write_text(out)
    print(f"wrote {OUT} ({len(out)} bytes); {len(DQ)} morphs, "
          f"{len(re.findall(r'&dq_', mac_dwerty))} dq refs on MAC_DWERTY, "
          f"{len(re.findall(r'&dq_', win_dwerty))} dq refs on WIN_DWERTY")


if __name__ == "__main__":
    main()
