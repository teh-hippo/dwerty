"""Exercise the patched upstream RTK target without the ARM toolchain."""

import pathlib
import shutil
import subprocess
import tempfile
import unittest


PATCH = pathlib.Path(__file__).parents[1] / "patches/0006-rtk-build-path.patch"
UPSTREAM_TARGET = """add_custom_target(rtk_post_build ALL
  COMMAND ${_PREPEND_HEADER} -t app_code -p build/zephyr/zmk.bin -m 1 -c sha256 -b 15
  COMMAND ${CMAKE_COMMAND} -E rm -f build/zephyr/zmk_MP.bin
  WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
)
add_dependencies(rtk_post_build zephyr_final)
"""


@unittest.skipUnless(shutil.which("cmake") and shutil.which("make"), "needs CMake and Make")
class RtkBuildPathTest(unittest.TestCase):
    def test_raw_default_build_and_explicit_packaging_in_custom_build_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            app = root / "app"
            app.mkdir()
            build = root / "custom build"
            tool = app / "prepend_header"
            tool.write_text(
                "#!/usr/bin/env python3\n"
                "import pathlib, sys\n"
                "image = pathlib.Path(sys.argv[sys.argv.index('-p') + 1])\n"
                "assert image.read_bytes() == b'raw'\n"
                "image.write_bytes(b'headerraw')\n"
                "image.with_name('zmk_MP.bin').write_bytes(b'mp')\n"
                "pathlib.Path('packaged').touch()\n"
            )
            tool.chmod(0o755)
            (app / "produce.cmake").write_text(
                'file(MAKE_DIRECTORY "${OUT}/zephyr")\n'
                'file(WRITE "${OUT}/zephyr/zmk.bin" "raw")\n'
            )
            (app / "CMakeLists.txt").write_text(
                "cmake_minimum_required(VERSION 3.20)\n"
                "project(rtk_path NONE)\n"
                'set(_PREPEND_HEADER "${CMAKE_CURRENT_SOURCE_DIR}/prepend_header")\n'
                "add_custom_target(zephyr_final ALL\n"
                '  COMMAND ${CMAKE_COMMAND} "-DOUT=${CMAKE_BINARY_DIR}"\n'
                '    -P "${CMAKE_CURRENT_SOURCE_DIR}/produce.cmake"\n'
                '  BYPRODUCTS "${CMAKE_BINARY_DIR}/zephyr/zmk.bin")\n'
                + UPSTREAM_TARGET
            )
            subprocess.run(["git", "apply", str(PATCH)], cwd=root, check=True)
            subprocess.run(
                ["cmake", "-S", str(app), "-B", str(build), "-G", "Unix Makefiles"],
                check=True, capture_output=True,
            )
            subprocess.run(
                ["cmake", "--build", str(build), "--parallel", "8"],
                check=True, capture_output=True,
            )
            image = build / "zephyr/zmk.bin"
            self.assertEqual(image.read_bytes(), b"raw")
            self.assertFalse((app / "packaged").exists())
            subprocess.run(
                ["cmake", "--build", str(build), "--target", "rtk_post_build", "--parallel", "8"],
                check=True, capture_output=True,
            )
            self.assertEqual(image.read_bytes(), b"headerraw")
            self.assertTrue((app / "packaged").exists())
            self.assertFalse((build / "zephyr/zmk_MP.bin").exists())


if __name__ == "__main__":
    unittest.main()
