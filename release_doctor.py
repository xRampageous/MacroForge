#!/usr/bin/env python3
"""Verify and repair MacroForge release assets.

This script is intentionally small and practical: it checks the updater
manifest, local build outputs, and published GitHub release assets. With
``--repair`` it uploads any missing or mismatched assets from ``dist`` without
requiring a rebuild.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from build_helper import sha256_file
from release_preflight import read_version


REPO = "xRampageous/MacroForge"


@dataclass(frozen=True)
class ReleaseAsset:
    name: str
    path: Path
    manifest_key: str | None = None

    def expected_url(self, version: str, repo: str) -> str:
        return f"https://github.com/{repo}/releases/download/v{version}/{self.name}"


def release_assets(root: Path, version: str, *, include_installer: bool = False) -> list[ReleaseAsset]:
    assets = [
        ReleaseAsset("MacroForge.exe", root / "dist" / "MacroForge.exe", "url"),
        ReleaseAsset(f"MacroForge-v{version}.zip", root / "dist" / f"MacroForge-v{version}.zip", "zip_url"),
        ReleaseAsset(f"MacroForge-v{version}.zip.sha256", root / "dist" / f"MacroForge-v{version}.zip.sha256"),
    ]
    installer = root / "installer" / f"MacroForge-Setup-v{version}.exe"
    if include_installer or installer.exists():
        assets.append(ReleaseAsset(f"MacroForge-Setup-v{version}.exe", installer))
    return assets


def run(args: list[str], *, capture: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        capture_output=capture,
        text=True,
        check=False,
    )


def gh_release(version: str, repo: str) -> tuple[dict | None, str | None]:
    result = run([
        "gh",
        "release",
        "view",
        f"v{version}",
        "--repo",
        repo,
        "--json",
        "tagName,url,assets,publishedAt",
    ])
    if result.returncode != 0:
        return None, (result.stderr or result.stdout or "gh release view failed").strip()
    try:
        return json.loads(result.stdout), None
    except json.JSONDecodeError as exc:
        return None, f"could not parse gh output: {exc}"


def local_digest(path: Path) -> str:
    return sha256_file(str(path))


def validate_release(
    root: Path,
    version: str,
    repo: str,
    *,
    online: bool = True,
    release: dict | None = None,
    require_installer: bool = False,
) -> tuple[list[str], list[str], dict | None]:
    errors: list[str] = []
    warnings: list[str] = []
    manifest_path = root / "update.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"update.json could not be read: {exc}"], warnings, release

    if manifest.get("version") != version:
        errors.append(f"update.json version {manifest.get('version')!r} does not match {version!r}")

    for asset in release_assets(root, version, include_installer=require_installer):
        if not asset.path.exists():
            errors.append(f"local release asset missing: {asset.path}")
            continue
        if asset.path.stat().st_size <= 0:
            errors.append(f"local release asset is empty: {asset.path}")
        if asset.manifest_key:
            expected = asset.expected_url(version, repo)
            if manifest.get(asset.manifest_key) != expected:
                errors.append(f"update.json {asset.manifest_key} does not match {expected}")

    if not online:
        return errors, warnings, release

    if release is None:
        release, release_error = gh_release(version, repo)
        if release_error:
            errors.append(f"could not read GitHub release: {release_error}")
            return errors, warnings, release
    if release and release.get("tagName") != f"v{version}":
        errors.append(f"release tag {release.get('tagName')!r} does not match v{version}")

    published = {asset.get("name"): asset for asset in (release or {}).get("assets", [])}
    for expected in release_assets(root, version, include_installer=require_installer):
        item = published.get(expected.name)
        if not item:
            errors.append(f"published release asset missing: {expected.name}")
            continue
        if expected.path.exists():
            local_size = expected.path.stat().st_size
            remote_size = int(item.get("size") or 0)
            if remote_size != local_size:
                errors.append(f"published {expected.name} size {remote_size} does not match local size {local_size}")
            digest = str(item.get("digest") or "")
            if digest.startswith("sha256:") and digest.removeprefix("sha256:") != local_digest(expected.path):
                errors.append(f"published {expected.name} SHA256 does not match local file")
            elif not digest:
                warnings.append(f"published {expected.name} does not expose a SHA256 digest")
        if expected.manifest_key:
            expected_url = expected.expected_url(version, repo)
            if item.get("url") != expected_url:
                errors.append(f"published {expected.name} URL does not match update.json contract")

    return errors, warnings, release


def repair_release(root: Path, version: str, repo: str, *, require_installer: bool = False) -> int:
    assets = release_assets(root, version, include_installer=require_installer)
    missing = [str(asset.path) for asset in assets if not asset.path.exists()]
    if missing:
        for path in missing:
            print(f"[ERROR] Cannot repair; local asset missing: {path}")
        return 1

    cmd = ["gh", "release", "upload", f"v{version}", "--repo", repo, "--clobber"]
    cmd.extend(str(asset.path) for asset in assets)
    print(f"[REPAIR] Uploading {len(assets)} asset(s) to v{version}...")
    result = run(cmd)
    if result.returncode != 0:
        print((result.stderr or result.stdout or "release upload failed").strip())
        return result.returncode or 1
    print("[REPAIR] Upload complete")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify or repair MacroForge release assets")
    parser.add_argument("version", nargs="?", help="Version to check, defaults to version.py")
    parser.add_argument("--repo", default=REPO, help="GitHub repository, owner/name")
    parser.add_argument("--offline", action="store_true", help="Only check local files and update.json")
    parser.add_argument("--repair", action="store_true", help="Upload local release assets with --clobber before verifying")
    parser.add_argument("--require-installer", action="store_true", help="Require the versioned Inno Setup installer asset")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    version = args.version or read_version(root)
    if not version:
        print("[ERROR] Could not determine version")
        return 1

    if args.repair:
        code = repair_release(root, version, args.repo, require_installer=args.require_installer)
        if code:
            return code

    errors, warnings, _release = validate_release(
        root,
        version,
        args.repo,
        online=not args.offline,
        require_installer=args.require_installer,
    )
    for warning in warnings:
        print(f"[WARN] {warning}")
    if errors:
        for error in errors:
            print(f"[ERROR] {error}")
        return 1
    scope = "local" if args.offline else "published"
    print(f"[OK] Release doctor passed for {scope} v{version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
