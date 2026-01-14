import pathlib
import re
import unittest

KEYMAP_PATH = pathlib.Path(__file__).resolve().parents[1] / "keymaps" / "keychron" / "v6_max" / "ansi_encoder" / "keymaps" / "dvorak_qwerty" / "keymap.c"
PAIR_RE = re.compile(r"\{\s*(KC_[A-Z0-9_]+)\s*,\s*(KC_[A-Z0-9_]+)\s*\}")


def _read_keymap_text() -> str:
    return KEYMAP_PATH.read_text(encoding="utf-8")


def _parse_mapping(text: str) -> dict[str, str]:
    block_match = re.search(r"qwerty_shortcut_map\[\]\s*=\s*\{(.*?)\};", text, re.S)
    if not block_match:
        raise AssertionError("mapping table not found in keymap.c")
    block = block_match.group(1)
    pairs = dict(PAIR_RE.findall(block))
    if not pairs:
        raise AssertionError("mapping table is empty")
    return pairs


def _parse_mod_mask(text: str, name: str) -> set[str]:
    line = next((line for line in text.splitlines() if name in line), "")
    if not line:
        raise AssertionError(f"{name} not found")
    return set(re.findall(r"MOD_MASK_[A-Z]+", line))


def _parse_layers(text: str) -> dict[str, int]:
    match = re.search(r"enum\s+layers\s*\{(.*?)\};", text, re.S)
    if not match:
        raise AssertionError("layers enum not found")
    body = match.group(1)
    names = []
    for entry in body.split(","):
        name = entry.strip()
        if not name:
            continue
        if name.startswith("//"):
            continue
        names.append(name)
    if not names:
        raise AssertionError("layers enum is empty")
    return {name: idx for idx, name in enumerate(names)}


class DummyFirmware:
    def __init__(self, mapping: dict[str, str], win_mask: set[str], mac_mask: set[str]) -> None:
        self.mapping = mapping
        self.win_mask = win_mask
        self.mac_mask = mac_mask
        self.active: str | None = None

    def _mask_for_layer(self, layer: str) -> set[str]:
        if layer == "MAC_BASE":
            return self.mac_mask
        if layer == "WIN_BASE":
            return self.win_mask
        return set()

    def process(self, keycode: str, pressed: bool, layer: str, mods: set[str]) -> tuple[str, str | None]:
        if not pressed:
            if self.active is not None:
                released = self.active
                self.active = None
                return ("unregister", released)
            return ("pass", None)

        if layer not in {"MAC_BASE", "WIN_BASE"}:
            return ("pass", None)

        if not (mods & self._mask_for_layer(layer)):
            return ("pass", None)

        mapped = self.mapping.get(keycode)
        if mapped is None:
            return ("pass", None)

        self.active = mapped
        return ("register", mapped)


class IntegrationSimulationTests(unittest.TestCase):
    def setUp(self) -> None:
        text = _read_keymap_text()
        self.mapping = _parse_mapping(text)
        self.win_mask = _parse_mod_mask(text, "SHORTCUT_MOD_MASK_WIN")
        self.mac_mask = _parse_mod_mask(text, "SHORTCUT_MOD_MASK_MAC")
        self.layers = _parse_layers(text)
        self.fw = DummyFirmware(self.mapping, self.win_mask, self.mac_mask)

    def test_win_ctrl_remaps_and_releases_even_if_mods_drop(self) -> None:
        mods = {"MOD_MASK_CTRL"}
        action, key = self.fw.process("KC_J", True, "WIN_BASE", mods)
        self.assertEqual(action, "register")
        self.assertEqual(key, self.mapping["KC_J"])

        mods = set()
        action, key = self.fw.process("KC_J", False, "WIN_BASE", mods)
        self.assertEqual(action, "unregister")
        self.assertEqual(key, self.mapping["KC_J"])

    def test_layers_present(self) -> None:
        for layer in ("MAC_BASE", "MAC_FN", "WIN_BASE", "WIN_FN"):
            self.assertIn(layer, self.layers)

    def test_shift_only_does_not_remap(self) -> None:
        mods = {"MOD_MASK_SHIFT"}
        action, key = self.fw.process("KC_J", True, "WIN_BASE", mods)
        self.assertEqual(action, "pass")
        self.assertIsNone(key)

    def test_mac_command_only(self) -> None:
        mods = {"MOD_MASK_CTRL"}
        action, key = self.fw.process("KC_J", True, "MAC_BASE", mods)
        self.assertEqual(action, "pass")
        self.assertIsNone(key)

        mods = {"MOD_MASK_GUI"}
        action, key = self.fw.process("KC_J", True, "MAC_BASE", mods)
        self.assertEqual(action, "register")
        self.assertEqual(key, self.mapping["KC_J"])

    def test_mac_alt_does_not_remap(self) -> None:
        mods = {"MOD_MASK_ALT"}
        action, key = self.fw.process("KC_J", True, "MAC_BASE", mods)
        self.assertEqual(action, "pass")
        self.assertIsNone(key)

    def test_win_alt_and_gui_remap(self) -> None:
        for mod in ("MOD_MASK_ALT", "MOD_MASK_GUI"):
            mods = {mod}
            action, key = self.fw.process("KC_J", True, "WIN_BASE", mods)
            self.assertEqual(action, "register")
            self.assertEqual(key, self.mapping["KC_J"])

            action, key = self.fw.process("KC_J", False, "WIN_BASE", set())
            self.assertEqual(action, "unregister")
            self.assertEqual(key, self.mapping["KC_J"])

    def test_common_shortcut_vectors_win(self) -> None:
        vectors = {
            "KC_J": "KC_C",
            "KC_K": "KC_V",
            "KC_Q": "KC_X",
            "KC_SCLN": "KC_Z",
            "KC_U": "KC_F",
        }
        mods = {"MOD_MASK_CTRL"}
        for dvorak_key, qwerty_key in vectors.items():
            action, key = self.fw.process(dvorak_key, True, "WIN_BASE", mods)
            self.assertEqual(action, "register")
            self.assertEqual(key, qwerty_key)
            self.fw.process(dvorak_key, False, "WIN_BASE", set())

    def test_common_shortcut_vectors_mac(self) -> None:
        vectors = {
            "KC_J": "KC_C",
            "KC_K": "KC_V",
            "KC_Q": "KC_X",
            "KC_SCLN": "KC_Z",
            "KC_U": "KC_F",
        }
        mods = {"MOD_MASK_GUI"}
        for dvorak_key, qwerty_key in vectors.items():
            action, key = self.fw.process(dvorak_key, True, "MAC_BASE", mods)
            self.assertEqual(action, "register")
            self.assertEqual(key, qwerty_key)
            self.fw.process(dvorak_key, False, "MAC_BASE", set())

    def test_shift_combo_does_not_block_remap(self) -> None:
        mods = {"MOD_MASK_CTRL", "MOD_MASK_SHIFT"}
        action, key = self.fw.process("KC_J", True, "WIN_BASE", mods)
        self.assertEqual(action, "register")
        self.assertEqual(key, self.mapping["KC_J"])
        self.fw.process("KC_J", False, "WIN_BASE", set())

    def test_unmapped_key_passes_through_even_with_mods(self) -> None:
        mods = {"MOD_MASK_CTRL"}
        action, key = self.fw.process("KC_A", True, "WIN_BASE", mods)
        self.assertEqual(action, "pass")
        self.assertIsNone(key)

    def test_release_after_layer_change_still_unregisters(self) -> None:
        mods = {"MOD_MASK_CTRL"}
        action, key = self.fw.process("KC_J", True, "WIN_BASE", mods)
        self.assertEqual(action, "register")
        self.assertEqual(key, self.mapping["KC_J"])

        action, key = self.fw.process("KC_J", False, "WIN_FN", set())
        self.assertEqual(action, "unregister")
        self.assertEqual(key, self.mapping["KC_J"])

    def test_fn_layers_do_not_remap(self) -> None:
        mods = {"MOD_MASK_CTRL"}
        action, key = self.fw.process("KC_J", True, "WIN_FN", mods)
        self.assertEqual(action, "pass")
        self.assertIsNone(key)

        mods = {"MOD_MASK_GUI"}
        action, key = self.fw.process("KC_J", True, "MAC_FN", mods)
        self.assertEqual(action, "pass")
        self.assertIsNone(key)


if __name__ == "__main__":
    unittest.main()
