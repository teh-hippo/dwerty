import pathlib
import re
import unittest

KEYMAP_PATH = pathlib.Path(__file__).resolve().parents[1] / "keymaps" / "keychron" / "v6_max" / "ansi_encoder" / "keymaps" / "dvorak_qwerty" / "keymap.c"

PAIR_RE = re.compile(r"\{\s*(KC_[A-Z0-9_]+)\s*,\s*(KC_[A-Z0-9_]+)\s*\}")

EXPECTED = {
    ("KC_QUOT", "KC_Q"),
    ("KC_COMM", "KC_W"),
    ("KC_DOT", "KC_E"),
    ("KC_P", "KC_R"),
    ("KC_Y", "KC_T"),
    ("KC_F", "KC_Y"),
    ("KC_G", "KC_U"),
    ("KC_C", "KC_I"),
    ("KC_R", "KC_O"),
    ("KC_L", "KC_P"),
    ("KC_SLSH", "KC_LBRC"),
    ("KC_EQL", "KC_RBRC"),
    ("KC_O", "KC_S"),
    ("KC_E", "KC_D"),
    ("KC_U", "KC_F"),
    ("KC_I", "KC_G"),
    ("KC_D", "KC_H"),
    ("KC_H", "KC_J"),
    ("KC_T", "KC_K"),
    ("KC_N", "KC_L"),
    ("KC_S", "KC_SCLN"),
    ("KC_MINS", "KC_QUOT"),
    ("KC_SCLN", "KC_Z"),
    ("KC_Q", "KC_X"),
    ("KC_J", "KC_C"),
    ("KC_K", "KC_V"),
    ("KC_X", "KC_B"),
    ("KC_B", "KC_N"),
    ("KC_W", "KC_COMM"),
    ("KC_V", "KC_DOT"),
    ("KC_Z", "KC_SLSH"),
    ("KC_LBRC", "KC_MINS"),
    ("KC_RBRC", "KC_EQL"),
}


class ShortcutMappingTests(unittest.TestCase):
    def test_mapping_table_matches_expected(self) -> None:
        text = KEYMAP_PATH.read_text(encoding="utf-8")
        block_match = re.search(r"qwerty_shortcut_map\[\]\s*=\s*\{(.*?)\};", text, re.S)
        self.assertIsNotNone(block_match, "mapping table not found in keymap.c")
        block = block_match.group(1)
        pairs = set(PAIR_RE.findall(block))
        self.assertEqual(pairs, EXPECTED)

    def test_shortcut_mod_mask_excludes_shift(self) -> None:
        text = KEYMAP_PATH.read_text(encoding="utf-8")
        mask_line = next((line for line in text.splitlines() if "SHORTCUT_MOD_MASK" in line), "")
        self.assertIn("MOD_MASK_CTRL", mask_line)
        self.assertIn("MOD_MASK_ALT", mask_line)
        self.assertIn("MOD_MASK_GUI", mask_line)
        self.assertNotIn("MOD_MASK_SHIFT", mask_line)

    def test_release_path_runs_before_mod_checks(self) -> None:
        text = KEYMAP_PATH.read_text(encoding="utf-8")
        func_start = text.find("bool process_record_user")
        self.assertNotEqual(func_start, -1, "process_record_user not found")

        brace_start = text.find("{", func_start)
        self.assertNotEqual(brace_start, -1, "process_record_user body not found")

        depth = 0
        func_end = -1
        for idx in range(brace_start, len(text)):
            if text[idx] == "{":
                depth += 1
            elif text[idx] == "}":
                depth -= 1
                if depth == 0:
                    func_end = idx
                    break

        self.assertNotEqual(func_end, -1, "process_record_user body not closed")
        body = text[brace_start:func_end]

        release_idx = body.find("if (!record->event.pressed)")
        layer_idx = body.find("qwerty_shortcuts_layer_active")
        self.assertNotEqual(release_idx, -1, "release handling not found in process_record_user")
        self.assertNotEqual(layer_idx, -1, "layer check not found in process_record_user")
        self.assertLess(release_idx, layer_idx, "release handling should occur before mod checks")


if __name__ == "__main__":
    unittest.main()
