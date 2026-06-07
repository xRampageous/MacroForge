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
