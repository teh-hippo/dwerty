import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
FIRMWARE_SH = ROOT / "scripts" / "firmware.sh"
CI_WORKFLOW = ROOT.parent / ".github" / "workflows" / "firmware-max.yml"

# Keychron only compiles dynamic debounce (and advertises FEATURE_DYNAMIC_DEBOUNCE,
# which makes the Launcher show "bounce time") when the V6 Max build sets
# debounce_type to "custom". Both build paths patch info.json to do this, so they
# must stay in sync.
FROM = '"debounce_type": "sym_eager_pk"'
TO = '"debounce_type": "custom"'


class DebouncePatchTest(unittest.TestCase):
    def assert_patches_debounce(self, path):
        # Both build paths embed the patch inside shell, so the JSON quotes are
        # backslash-escaped; strip backslashes before matching.
        text = path.read_text().replace("\\", "")
        self.assertIn(FROM, text, f"{path.name} should match the upstream debounce_type")
        self.assertIn(TO, text, f"{path.name} should patch debounce_type to custom")

    def test_firmware_script_patches_debounce(self):
        self.assert_patches_debounce(FIRMWARE_SH)

    def test_ci_workflow_patches_debounce(self):
        self.assert_patches_debounce(CI_WORKFLOW)


if __name__ == "__main__":
    unittest.main()
