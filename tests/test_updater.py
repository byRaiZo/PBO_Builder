import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pbobuilder.updater import (
    UpdateError,
    check_for_update,
    find_release_assets,
    is_newer_version,
    parse_sha256_text,
    parse_version,
    release_to_update_info,
    verify_sha256,
)


def make_release(tag_name="v1.0.1", prerelease=False):
    return {
        "tag_name": tag_name,
        "draft": False,
        "prerelease": prerelease,
        "html_url": "https://github.com/byRaiZo/PBO_Builder/releases/tag/" + tag_name,
        "assets": [
            {
                "name": f"PBO_Builder_byRaiZo-{tag_name}-win64.zip",
                "browser_download_url": "https://example.test/app.zip",
            },
            {
                "name": f"PBO_Builder_byRaiZo-{tag_name}-win64.zip.sha256",
                "browser_download_url": "https://example.test/app.zip.sha256",
            },
        ],
    }


class VersionTests(unittest.TestCase):
    def test_semver_parsing_accepts_plain_and_tagged_versions(self):
        self.assertEqual(parse_version("1.0.0"), (1, 0, 0))
        self.assertEqual(parse_version("v1.2.3"), (1, 2, 3))

    def test_semver_parsing_rejects_prerelease_and_bad_strings(self):
        self.assertIsNone(parse_version("v1.0.0-beta"))
        self.assertIsNone(parse_version("1.0"))
        self.assertIsNone(parse_version("latest"))

    def test_newer_version_comparison(self):
        self.assertTrue(is_newer_version("1.0.0", "1.0.1"))
        self.assertFalse(is_newer_version("v1.0.0", "1.0.0"))
        self.assertFalse(is_newer_version("1.0.1", "1.0.0"))
        self.assertFalse(is_newer_version("bad", "1.0.1"))


class ReleaseAssetTests(unittest.TestCase):
    def test_release_to_update_info_selects_zip_and_checksum_assets(self):
        update_info = release_to_update_info(make_release(), current_version="1.0.0")

        self.assertIsNotNone(update_info)
        self.assertEqual(update_info.version, "1.0.1")
        self.assertEqual(update_info.tag_name, "v1.0.1")
        self.assertTrue(update_info.zip_name.endswith("-win64.zip"))
        self.assertTrue(update_info.sha256_name.endswith(".zip.sha256"))

    def test_release_to_update_info_ignores_prerelease_and_invalid_tag(self):
        self.assertIsNone(release_to_update_info(make_release("v1.0.1-beta"), "1.0.0"))
        self.assertIsNone(release_to_update_info(make_release("latest"), "1.0.0"))
        self.assertIsNone(release_to_update_info(make_release("v1.0.1", prerelease=True), "1.0.0"))

    def test_release_assets_missing_checksum_are_rejected(self):
        release = make_release()
        release["assets"] = release["assets"][:1]

        self.assertEqual(find_release_assets(release, "1.0.1"), (None, None))
        self.assertIsNone(release_to_update_info(release, "1.0.0"))


class ChecksumTests(unittest.TestCase):
    def test_parse_sha256_text_accepts_common_file_format(self):
        expected = "a" * 64
        self.assertEqual(parse_sha256_text(f"{expected}  file.zip\n"), expected)

    def test_verify_sha256_rejects_mismatch(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir, "payload.zip")
            file_path.write_bytes(b"payload")

            with self.assertRaises(UpdateError):
                verify_sha256(file_path, "0" * 64)


class SourceModeTests(unittest.TestCase):
    def test_check_for_update_skips_non_frozen_source_mode(self):
        with patch("pbobuilder.updater.fetch_latest_release") as fetch_latest_release:
            self.assertIsNone(check_for_update(current_version="1.0.0", frozen=False))
            fetch_latest_release.assert_not_called()


if __name__ == "__main__":
    unittest.main()
