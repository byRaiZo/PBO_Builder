import os
import tempfile
import unittest
from pathlib import Path

from pbobuilder.files import get_dangerous_temp_root_reason
from pbobuilder.filters import should_skip_dir, should_skip_file
from pbobuilder.pbo import pack_pbo, read_packed_pbo_prefix
from pbobuilder.targets import detect_addon_targets, get_pbo_prefix, read_pbo_prefix_file


class FilterTests(unittest.TestCase):
    def test_protected_build_files_are_not_excluded(self):
        self.assertFalse(should_skip_file("config.cpp", ["*.cpp"]))
        self.assertFalse(should_skip_file("config.bin", ["*.bin"]))
        self.assertFalse(should_skip_file("model.p3d", ["*.p3d"]))
        self.assertFalse(should_skip_file("part_damage.rvmat", ["*.rvmat"]))
        self.assertFalse(should_skip_file("part_destruct.rvmat", ["*.rvmat"]))

    def test_default_excludes(self):
        self.assertTrue(should_skip_dir(".git"))
        self.assertTrue(should_skip_dir("__pycache__"))
        self.assertTrue(should_skip_file("thumbs.db"))
        self.assertTrue(should_skip_file("old.delete"))


class TargetDetectionTests(unittest.TestCase):
    def test_detects_root_addon_when_root_has_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "config.cpp").write_text("class CfgPatches {};", encoding="utf-8")

            self.assertEqual(detect_addon_targets(temp_dir, ""), [(Path(temp_dir).name, temp_dir)])

    def test_detects_config_subfolders_and_ignores_output_folders(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            addon_a = Path(temp_dir, "AddonA")
            addon_b = Path(temp_dir, "AddonB")
            output = Path(temp_dir, "Addons")
            addon_a.mkdir()
            addon_b.mkdir()
            output.mkdir()
            Path(addon_a, "config.cpp").write_text("class CfgPatches {};", encoding="utf-8")
            Path(addon_b, "config.cpp").write_text("class CfgPatches {};", encoding="utf-8")
            Path(output, "config.cpp").write_text("ignored", encoding="utf-8")

            targets = detect_addon_targets(temp_dir, str(output))

            self.assertEqual([name for name, _path in targets], ["AddonA", "AddonB"])


class PrefixTests(unittest.TestCase):
    def test_reads_pboprefix_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "$PBOPREFIX$").write_text("my/mod/path\n", encoding="utf-8")

            self.assertEqual(read_pbo_prefix_file(temp_dir), r"my\mod\path")
            self.assertEqual(get_pbo_prefix("fallback", temp_dir), r"my\mod\path")

    def test_prefix_falls_back_to_pbo_name(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            self.assertEqual(get_pbo_prefix("my_addon", temp_dir), "my_addon")


class TempSafetyTests(unittest.TestCase):
    def test_temp_root_overlapping_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir, "source")
            temp_root = source / "temp"
            source.mkdir()

            reason = get_dangerous_temp_root_reason(str(temp_root), str(source), "")

            self.assertIn("Source root", reason)

    def test_temp_root_overlapping_output_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir, "output")
            temp_root = output / "temp"
            output.mkdir()

            reason = get_dangerous_temp_root_reason(str(temp_root), "", str(output))

            self.assertIn("Output root", reason)


class PboPackTests(unittest.TestCase):
    def test_pack_pbo_writes_readable_prefix(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir, "source")
            output = Path(temp_dir, "out", "addon.pbo")
            source.mkdir()
            Path(source, "config.bin").write_bytes(b"raP\0")
            Path(source, "data.txt").write_text("hello", encoding="utf-8")

            pack_pbo(str(source), str(output), r"my\addon", lambda _message: None)

            self.assertTrue(output.is_file())
            self.assertGreater(output.stat().st_size, 0)
            self.assertEqual(read_packed_pbo_prefix(str(output)), r"my\addon")


if __name__ == "__main__":
    unittest.main()
