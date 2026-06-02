#!/usr/bin/env python3
"""Verify a published MacroForge release and its updater metadata."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from build_helper import sha256_file
from release_preflight import read_version


REPO = "xRampageous/MacroForge"


def _run_gh_release(version: str, repo: str = REPO) -> dict:
    result = subprocess.run(
        [
            "gh",
            "release",
            "view",
            f"v{version}",
            "--repo",
            repo,
            "--json",
            "tagName,url,assets,publishedAt",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def verify_post_release(root: Path, version: str | None = None, release: dict | None = None) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    version = version or read_version(root)
    manifest = json.loads((root / "update.json").read_text(encoding="utf-8"))
    expected_name = f"MacroForge-v{version}.zip"
    expected_url = f"https://github.com/{REPO}/releases/download/v{version}/{expected_name}"

    if manifest.get("version") != version:
        errors.append(f"update.json version {manifest.get('version')!r} does not match {version!r}")
    if manifest.get("zip_url") != expected_url:
        errors.append("update.json zip_url does not match the published asset URL")

    release = release or _run_gh_release(version)
    if release.get("tagName") != f"v{version}":
        errors.append(f"release tag {release.get('tagName')!r} does not match v{version}")
    assets = release.get("assets") or []
    asset = next((item for item in assets if item.get("name") == expected_name), None)
    if not asset:
        errors.append(f"release asset missing: {expected_name}")
        return errors, warnings

    if asset.get("url") != expected_url:
        errors.append("release asset URL does not match update.json zip_url")
    if int(asset.get("size") or 0) <= 0:
        errors.append("release asset size is empty")

    local_zip = root / "dist" / expected_name
    if local_zip.exists():
        local_size = local_zip.stat().st_size
        if int(asset.get("size") or 0) != local_size:
            errors.append(f"release asset size {asset.get('size')} does not match local ZIP size {local_size}")
        digest = asset.get("digest") or ""
        if digest.startswith("sha256:"):
            local_digest = sha256_file(str(local_zip))
            if digest.removeprefix("sha256:") != local_digest:
                errors.append("release asset SHA256 digest does not match local ZIP")
        else:
            warnings.append("release asset does not expose a SHA256 digest")
    else:
        warnings.append(f"local ZIP not found for digest comparison: {local_zip}")
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("version", nargs="?", help="Version to verify, defaults to version.py")
    parser.add_argument("--repo", default=REPO, help="GitHub repository, owner/name")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    try:
        release = _run_gh_release(args.version or read_version(root), repo=args.repo)
    except Exception as exc:
        print(f"[ERROR] Could not read GitHub release: {exc}")
        return 1
    errors, warnings = verify_post_release(root, args.version, release)
    for warning in warnings:
        print(f"[WARN] {warning}")
    if errors:
        for error in errors:
            print(f"[ERROR] {error}")
        return 1
    print("[OK] Post-release verification passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
