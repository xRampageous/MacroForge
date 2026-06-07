#!/usr/bin/env python3
"""Verify a published MacroForge release and its updater metadata."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from release_doctor import validate_release
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
    version = version or read_version(root)
    return validate_release(root, version, REPO, online=True, release=release)[:2]


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
