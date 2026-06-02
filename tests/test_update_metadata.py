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
import post_release_verify
import release_preflight
import support_bundle
import update_health
import updater
from ui import diagnostics_panel
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
                    manifest = json.loads(zf.read("artifact_manifest.json").decode("utf-8"))
                digest_text = Path("dist/MacroForge-v9.9.9.zip.sha256").read_text(encoding="utf-8")
            finally:
                os.chdir(cwd)

        self.assertIn("MacroForge.exe", names)
        self.assertIn("_internal/module.py", names)
        self.assertIn("artifact_manifest.json", names)
        self.assertEqual(manifest["version"], "9.9.9")
        self.assertEqual(manifest["zip_name"], "MacroForge-v9.9.9.zip")
        self.assertIn("See the adjacent .sha256 sidecar", manifest["zip_sha256_note"])
        self.assertIn("MacroForge-v9.9.9.zip", digest_text)
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

    def test_release_preflight_rejects_bad_digest_sidecar(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "version.py").write_text('VERSION = "9.9.9"\n', encoding="utf-8")
            (root / "update.json").write_text(
                json.dumps({
                    "version": "9.9.9",
                    "url": "https://github.com/xRampageous/MacroForge/releases/download/v9.9.9/MacroForge.exe",
                    "zip_url": "https://github.com/xRampageous/MacroForge/releases/download/v9.9.9/MacroForge-v9.9.9.zip",
                    "notes": "test",
                }),
                encoding="utf-8",
            )
            dist = root / "dist"
            dist.mkdir()
            zip_path = dist / "MacroForge-v9.9.9.zip"
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("MacroForge.exe", "exe")
                zf.writestr("_internal/module.py", "module")
                zf.writestr("artifact_manifest.json", "{}")
            Path(f"{zip_path}.sha256").write_text("bad  MacroForge-v9.9.9.zip\n", encoding="utf-8")

            errors, _warnings = release_preflight.validate_release(root, require_clean=False)

        self.assertTrue(any("digest sidecar does not match" in error for error in errors))

    def test_release_preflight_warns_when_zip_exceeds_size_budget(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "version.py").write_text('VERSION = "9.9.9"\n', encoding="utf-8")
            (root / "update.json").write_text(
                json.dumps({
                    "version": "9.9.9",
                    "url": "https://github.com/xRampageous/MacroForge/releases/download/v9.9.9/MacroForge.exe",
                    "zip_url": "https://github.com/xRampageous/MacroForge/releases/download/v9.9.9/MacroForge-v9.9.9.zip",
                    "notes": "test",
                }),
                encoding="utf-8",
            )
            dist = root / "dist"
            dist.mkdir()
            zip_path = dist / "MacroForge-v9.9.9.zip"
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("MacroForge.exe", "exe")
                zf.writestr("_internal/module.py", "module")
                zf.writestr("artifact_manifest.json", "{}")
            Path(f"{zip_path}.sha256").write_text(
                f"{build_helper.sha256_file(str(zip_path))}  MacroForge-v9.9.9.zip\n",
                encoding="utf-8",
            )

            with patch.object(release_preflight, "ZIP_SIZE_WARNING_BYTES", 1):
                errors, warnings = release_preflight.validate_release(root, require_clean=False)

        self.assertEqual(errors, [])
        self.assertTrue(any("release ZIP is large" in warning for warning in warnings))

    def test_post_release_verifier_matches_fake_release_asset(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "version.py").write_text('VERSION = "9.9.9"\n', encoding="utf-8")
            (root / "update.json").write_text(
                json.dumps({
                    "version": "9.9.9",
                    "url": "https://github.com/xRampageous/MacroForge/releases/download/v9.9.9/MacroForge.exe",
                    "zip_url": "https://github.com/xRampageous/MacroForge/releases/download/v9.9.9/MacroForge-v9.9.9.zip",
                    "notes": "test",
                }),
                encoding="utf-8",
            )
            dist = root / "dist"
            dist.mkdir()
            zip_path = dist / "MacroForge-v9.9.9.zip"
            zip_path.write_bytes(b"release zip")
            digest = build_helper.sha256_file(str(zip_path))
            release = {
                "tagName": "v9.9.9",
                "assets": [{
                    "name": "MacroForge-v9.9.9.zip",
                    "url": "https://github.com/xRampageous/MacroForge/releases/download/v9.9.9/MacroForge-v9.9.9.zip",
                    "size": zip_path.stat().st_size,
                    "digest": f"sha256:{digest}",
                }],
            }

            errors, warnings = post_release_verify.verify_post_release(root, "9.9.9", release)

        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])


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

    def test_updater_dry_run_reports_bad_manifest_and_url(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            health_file = Path(tmpdir) / "update_health.json"
            with (
                patch("update_health.health_path", return_value=health_file),
                patch("updater._work_dir", return_value=Path(tmpdir)),
            ):
                result = updater.updater_dry_run({"version": "9.9.9", "zip_url": "ftp://example.com/update.zip"})
                health = update_health.load(health_file)

        self.assertFalse(result["ready"])
        self.assertTrue(any("http(s)" in error for error in result["errors"]))
        self.assertEqual(health["last_dry_run"]["event"], "dry_run_failed")

    def test_update_health_marks_startup_after_handoff(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            health_file = Path(tmpdir) / "update_health.json"
            update_health.record(
                "handoff_started",
                health_file,
                status="started",
                from_version="1.0.0",
                to_version="1.0.1",
            )

            update_health.mark_startup("1.0.1", health_file)
            lines = update_health.summary_lines(health_file)
            health = update_health.load(health_file)
            status = update_health.overall_status(health_file)

        self.assertEqual(health["last_startup"]["event"], "startup_success")
        self.assertEqual(status, "Completed")
        self.assertIn("1.0.1", "\n".join(lines))

    def test_update_health_clear_resets_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            health_file = Path(tmpdir) / "update_health.json"
            update_health.record("check_failed", health_file, status="failed", error="timeout")
            update_health.clear(health_file)
            health = update_health.load(health_file)
            status = update_health.overall_status(health_file)

        self.assertEqual(health["events"], [])
        self.assertIsNone(health["last_check"])
        self.assertEqual(status, "Unknown")

    def test_support_bundle_contains_diagnostics_and_update_health(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            health_file = Path(tmpdir) / "update_health.json"
            bundle_path = Path(tmpdir) / "support.zip"
            active_profile = Path(tmpdir) / "active.json"
            active_profile.write_text('{"profile": "active"}', encoding="utf-8")
            update_health.record("check_failed", health_file, status="failed", error="timeout")
            with patch("update_health.health_path", return_value=health_file):
                support_bundle.create_support_bundle(
                    bundle_path,
                    ["Version: test", "Update health check: failed"],
                    {"profile": "default"},
                    active_profile_path=active_profile,
                )

            with zipfile.ZipFile(bundle_path, "r") as zf:
                names = set(zf.namelist())
                diagnostics = zf.read("diagnostics.txt").decode("utf-8")
                version_info = json.loads(zf.read("version.json").decode("utf-8"))

        self.assertIn("diagnostics.txt", names)
        self.assertIn("update_health.json", names)
        self.assertIn("version.json", names)
        self.assertIn("profiles/active.json", names)
        self.assertIn("Update health check: failed", diagnostics)
        self.assertEqual(version_info["profile"], "default")

    def test_diagnostics_validation_uses_latest_health_manifest(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            health_file = Path(tmpdir) / "update_health.json"
            update_health.record(
                "manifest_valid",
                health_file,
                status="valid",
                remote_version="9.9.10",
                zip_url="https://example.com/MacroForge-v9.9.10.zip",
                url="",
            )
            with patch("update_health.health_path", return_value=health_file):
                manifest = diagnostics_panel.latest_manifest_for_validation()

        self.assertEqual(manifest["version"], "9.9.10")
        self.assertEqual(manifest["zip_url"], "https://example.com/MacroForge-v9.9.10.zip")

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
