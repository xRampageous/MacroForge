"""Tests for the release command surface."""
from argparse import Namespace
from unittest.mock import patch

import release_cli


def test_parser_accepts_publish_existing_build_dry_run():
    parser = release_cli.build_parser()

    args = parser.parse_args(["publish", "9.9.9", "--allow-dirty", "--dry-run"])

    assert args.command == "publish"
    assert args.version == "9.9.9"
    assert args.allow_dirty is True
    assert args.dry_run is True


def test_parser_accepts_clean_and_bump_commands():
    parser = release_cli.build_parser()

    clean_args = parser.parse_args(["clean", "--dry-run", "--include-build"])
    bump_args = parser.parse_args(["bump", "minor"])

    assert clean_args.command == "clean"
    assert clean_args.dry_run is True
    assert clean_args.include_build is True
    assert bump_args.command == "bump"
    assert bump_args.part == "minor"


def test_publish_dry_run_does_not_create_or_upload_release():
    args = Namespace(
        version="9.9.9",
        repo="xRampageous/MacroForge",
        allow_dirty=True,
        skip_preflight=True,
        dry_run=True,
    )

    with (
        patch.object(release_cli, "ensure_release") as ensure_release,
        patch.object(release_cli, "upload_release_assets") as upload_release_assets,
        patch.object(release_cli, "print_asset_table") as print_asset_table,
    ):
        result = release_cli.cmd_publish(args)

    assert result == 0
    ensure_release.assert_not_called()
    upload_release_assets.assert_not_called()
    print_asset_table.assert_called_once_with("9.9.9", "xRampageous/MacroForge")


def test_clean_removes_generated_clutter_without_dist(tmp_path):
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / ".pytest_cache").mkdir()
    (tmp_path / "debug.log").write_text("log", encoding="utf-8")
    (tmp_path / "macroforge_session.json").write_text("{}", encoding="utf-8")
    (tmp_path / "test_download.zip").write_text("zip", encoding="utf-8")
    (tmp_path / "upload_release.bat").write_text("old", encoding="utf-8")
    (tmp_path / "dist").mkdir()

    with patch.object(release_cli, "ROOT", tmp_path):
        result = release_cli.cmd_clean(Namespace(dry_run=False, include_build=False))

    assert result == 0
    assert not (tmp_path / "__pycache__").exists()
    assert not (tmp_path / ".pytest_cache").exists()
    assert not (tmp_path / "debug.log").exists()
    assert not (tmp_path / "macroforge_session.json").exists()
    assert not (tmp_path / "test_download.zip").exists()
    assert not (tmp_path / "upload_release.bat").exists()
    assert (tmp_path / "dist").exists()


def test_clean_dry_run_keeps_files(tmp_path):
    (tmp_path / "debug.log").write_text("log", encoding="utf-8")

    with patch.object(release_cli, "ROOT", tmp_path):
        result = release_cli.cmd_clean(Namespace(dry_run=True, include_build=False))

    assert result == 0
    assert (tmp_path / "debug.log").exists()


def test_bump_updates_version_file(tmp_path):
    version_file = tmp_path / "version.py"
    version_file.write_text('VERSION = "1.2.3"\n', encoding="utf-8")

    with patch.object(release_cli, "ROOT", tmp_path):
        result = release_cli.cmd_bump(Namespace(part="minor"))

    assert result == 0
    assert version_file.read_text(encoding="utf-8") == 'VERSION = "1.3.0"\n'
