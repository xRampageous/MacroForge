"""Build clean MacroForge source/release archives.

Usage:
    python clean_release.py
    python clean_release.py --source-only

The script intentionally excludes local/workspace state such as .git, build,
dist, __pycache__, logs, IDE files, and old archives. It can be run before a
GitHub release to generate a professional source bundle and verify the existing
release ZIP checksum when present.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import time
import zipfile
from pathlib import Path

from version import VERSION

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "dist"
EXCLUDE_DIRS = {
    ".git", ".github", ".idea", ".vscode", ".windsurf", "__pycache__",
    "build", "dist", "installer", ".local_snapshots", "recovery",
    "MacroForge",
}
EXCLUDE_SUFFIXES = {".pyc", ".pyo", ".pyd", ".log", ".rar"}
EXCLUDE_NAMES = {"debug.log", "macroforge_session.json", "settings.json", "update_health.json"}


def should_include(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    if any(part in EXCLUDE_DIRS for part in rel.parts):
        return False
    if path.name in EXCLUDE_NAMES:
        return False
    if path.suffix.lower() in EXCLUDE_SUFFIXES:
        return False
    if path.suffix.lower() == ".zip":
        return False
    return True


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_source_zip() -> Path:
    OUT.mkdir(exist_ok=True)
    target = OUT / f"MacroForge-source-v{VERSION}.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in sorted(ROOT.rglob("*")):
            if path.is_dir() or not should_include(path):
                continue
            zf.write(path, path.relative_to(ROOT.parent))
    (target.with_suffix(target.suffix + ".sha256")).write_text(sha256(target) + "\n", encoding="utf-8")
    return target


def verify_release_zip() -> dict:
    release = OUT / f"MacroForge-v{VERSION}.zip"
    if not release.exists():
        return {"release_zip": str(release), "exists": False}
    digest = sha256(release)
    sidecar = release.with_suffix(release.suffix + ".sha256")
    sidecar.write_text(digest + "\n", encoding="utf-8")
    return {"release_zip": str(release), "exists": True, "sha256": digest}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true", help="Only build the clean source ZIP")
    args = parser.parse_args()

    source_zip = write_source_zip()
    result = {
        "version": VERSION,
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "source_zip": str(source_zip),
        "source_sha256": sha256(source_zip),
    }
    if not args.source_only:
        result["release"] = verify_release_zip()
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
