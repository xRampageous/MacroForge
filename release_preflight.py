#!/usr/bin/env python3
"""Validate release metadata and ZIP contents before upload."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path


ARCHIVE_SUFFIXES = (".zip", ".7z", ".rar")
ZIP_SIZE_WARNING_BYTES = 120 * 1024 * 1024


def read_version(root: Path) -> str:
    text = (root / "version.py").read_text(encoding="utf-8")
    match = re.search(r'VERSION\s*=\s*"([^"]+)"', text)
    return match.group(1) if match else ""


def git_is_clean(root: Path) -> bool:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0 and not result.stdout.strip()


def validate_release(root: Path, require_clean: bool = True) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    version = read_version(root)
    if not version:
        errors.append("version.py does not contain VERSION")
    manifest_path = root / "update.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"update.json could not be read: {exc}"], warnings

    expected_zip_url = f"https://github.com/xRampageous/MacroForge/releases/download/v{version}/MacroForge-v{version}.zip"
    expected_exe_url = f"https://github.com/xRampageous/MacroForge/releases/download/v{version}/MacroForge.exe"
    if manifest.get("version") != version:
        errors.append(f"update.json version {manifest.get('version')!r} does not match version.py {version!r}")
    if manifest.get("zip_url") != expected_zip_url:
        errors.append("update.json zip_url does not match the expected release ZIP URL")
    if manifest.get("url") != expected_exe_url:
        errors.append("update.json url does not match the expected legacy EXE URL")
    if not str(manifest.get("notes", "")).strip():
        errors.append("update.json notes must not be empty")

    exe_path = root / "dist" / "MacroForge.exe"
    if not exe_path.exists():
        errors.append(f"legacy EXE asset missing: {exe_path}")
    elif exe_path.stat().st_size <= 0:
        errors.append(f"legacy EXE asset is empty: {exe_path}")
    else:
        onedir_exe = root / "dist" / "MacroForge" / "MacroForge.exe"
        if onedir_exe.exists() and exe_path.stat().st_size <= onedir_exe.stat().st_size:
            errors.append("legacy EXE asset appears to be the onedir launcher, not a standalone onefile build")

    zip_path = root / "dist" / f"MacroForge-v{version}.zip"
    if not zip_path.exists():
        errors.append(f"release ZIP missing: {zip_path}")
    else:
        zip_size = zip_path.stat().st_size
        if zip_size > ZIP_SIZE_WARNING_BYTES:
            warnings.append(
                f"release ZIP is large: {zip_size / (1024 * 1024):.1f} MB "
                f"(warning threshold {ZIP_SIZE_WARNING_BYTES / (1024 * 1024):.0f} MB)"
            )
        digest_path = Path(f"{zip_path}.sha256")
        if not digest_path.exists():
            errors.append(f"release ZIP digest sidecar missing: {digest_path}")
        else:
            actual = hashlib.sha256(zip_path.read_bytes()).hexdigest()
            recorded = digest_path.read_text(encoding="utf-8").split()[0]
            if recorded != actual:
                errors.append("release ZIP digest sidecar does not match ZIP contents")
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                names = zf.namelist()
                if "MacroForge.exe" not in names:
                    errors.append("release ZIP does not contain MacroForge.exe at the root")
                if "artifact_manifest.json" not in names:
                    errors.append("release ZIP does not contain artifact_manifest.json")
                if "_internal/" not in {name if name.endswith("/") else os.path.dirname(name) + "/" for name in names}:
                    warnings.append("release ZIP does not appear to contain an _internal folder")
                nested = [name for name in names if name.lower().endswith(ARCHIVE_SUFFIXES)]
                if nested:
                    errors.append("release ZIP contains nested archives: " + ", ".join(nested[:5]))
        except Exception as exc:
            errors.append(f"release ZIP could not be inspected: {exc}")

    if require_clean and not git_is_clean(root):
        errors.append("git working tree is dirty")
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-dirty", action="store_true", help="Do not fail on a dirty git working tree")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    errors, warnings = validate_release(root, require_clean=not args.allow_dirty)
    for warning in warnings:
        print(f"[WARN] {warning}")
    if errors:
        for error in errors:
            print(f"[ERROR] {error}")
        return 1
    print("[OK] Release preflight passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
