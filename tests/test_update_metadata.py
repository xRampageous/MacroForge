"""Regression tests for release updater metadata."""
import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import build_helper
import updater
from version import VERSION


REPO_ROOT = Path(__file__).resolve().parents[1]


class TestUpdateMetadata(unittest.TestCase):
    def test_checked_in_update_json_has_zip_and_legacy_exe_url(self):
        data = json.loads((REPO_ROOT / "update.json").read_text(encoding="utf-8"))

        self.assertEqual(data["version"], VERSION)
        self.assertIn(f"/releases/download/v{VERSION}/", data["zip_url"])
        self.assertTrue(data["zip_url"].endswith(f"MacroForge-v{VERSION}.zip"))
        self.assertIn(f"/releases/download/v{VERSION}/", data["url"])
        self.assertTrue(data["url"].endswith("MacroForge.exe"))
        self.assertTrue(data.get("notes"))

    def test_build_helper_writes_complete_manifest(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                Path("update.json").write_text(
                    json.dumps({"version": "9.9.9", "notes": "keep me"}),
                    encoding="utf-8",
                )

                build_helper.write_update_json("9.9.9")
                data = json.loads(Path("update.json").read_text(encoding="utf-8"))
            finally:
                os.chdir(cwd)

        self.assertEqual(data["version"], "9.9.9")
        self.assertEqual(data["notes"], "keep me")
        self.assertEqual(
            data["url"],
            "https://github.com/xRampageous/MacroForge/releases/download/v9.9.9/MacroForge.exe",
        )
        self.assertEqual(
            data["zip_url"],
            "https://github.com/xRampageous/MacroForge/releases/download/v9.9.9/MacroForge-v9.9.9.zip",
        )

    def test_release_zip_skips_nested_archives(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                app_dir = Path("dist") / "MacroForge"
                internal_dir = app_dir / "_internal"
                internal_dir.mkdir(parents=True)
                (app_dir / "MacroForge.exe").write_text("exe", encoding="utf-8")
                (internal_dir / "module.py").write_text("module", encoding="utf-8")
                (app_dir / "old.zip").write_text("zip", encoding="utf-8")
                (internal_dir / "old.7z").write_text("7z", encoding="utf-8")

                build_helper.create_update_zip("9.9.9")
                with zipfile.ZipFile(Path("dist") / "MacroForge-v9.9.9.zip", "r") as zf:
                    names = zf.namelist()
            finally:
                os.chdir(cwd)

        self.assertIn("MacroForge.exe", names)
        self.assertIn("_internal/module.py", names)
        self.assertNotIn("old.zip", names)
        self.assertNotIn("_internal/old.7z", names)

    def test_clean_release_zips_removes_stale_top_level_archives(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            dist = Path(tmpdir) / "dist"
            dist.mkdir()
            stale = dist / "MacroForge-v1.0.0.zip"
            keep = dist / "MacroForge-v9.9.9.zip"
            stale.write_text("old", encoding="utf-8")
            keep.write_text("new", encoding="utf-8")

            removed = build_helper.clean_release_zips(str(dist), keep=str(keep))
            self.assertEqual(len(removed), 1)
            self.assertFalse(stale.exists())
            self.assertTrue(keep.exists())


class TestUpdaterValidation(unittest.TestCase):
    def test_manifest_validation_rejects_malformed_metadata(self):
        cases = [
            ({}, "version is missing"),
            ({"version": "3.x.1", "zip_url": "https://example.com/a.zip", "notes": "x"}, "invalid version"),
            ({"version": "3.1.2", "notes": "x"}, "zip_url or url"),
            ({"version": "3.1.2", "zip_url": "https://example.com/a.zip", "notes": ""}, "notes"),
        ]

        for manifest, expected in cases:
            with self.subTest(manifest=manifest):
                self.assertTrue(any(expected in error for error in updater.validate_manifest(manifest)))

    def test_perform_update_rejects_manifest_before_download(self):
        with patch("updater.urllib.request.urlopen") as urlopen_mock:
            self.assertFalse(updater.perform_update({"version": "bad"}))
        urlopen_mock.assert_not_called()

    def test_safe_extract_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = Path(tmpdir) / "bad.zip"
            extract_dir = Path(tmpdir) / "out"
            extract_dir.mkdir()
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("../escape.txt", "nope")

            with zipfile.ZipFile(zip_path, "r") as zf:
                with self.assertRaises(ValueError):
                    updater._safe_extract_zip(zf, extract_dir)

            self.assertFalse((Path(tmpdir) / "escape.txt").exists())


if __name__ == "__main__":
    unittest.main()
