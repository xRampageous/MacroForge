#!/usr/bin/env python3
"""Helper script for build.bat — extracts version, writes update.json, creates ZIP."""

import json
import os
import re
import sys
import hashlib
import socket
import subprocess
import zipfile
from datetime import datetime, timezone


def get_version() -> str:
    with open("version.py", "r", encoding="utf-8") as f:
        m = re.search(r'VERSION\s*=\s*"([^"]+)"', f.read())
    return m.group(1) if m else ""


def write_update_json(version: str) -> None:
    # Preserve existing notes if present
    existing_notes = f"Release v{version}"
    try:
        with open("update.json", "r", encoding="utf-8") as f:
            old = json.load(f)
            if old.get("version") == version and old.get("notes"):
                existing_notes = old["notes"]
    except Exception:
        pass
    data = {
        "version": version,
        "url": f"https://github.com/xRampageous/MacroForge/releases/download/v{version}/MacroForge.exe",
        "zip_url": f"https://github.com/xRampageous/MacroForge/releases/download/v{version}/MacroForge-v{version}.zip",
        "notes": existing_notes,
    }
    with open("update.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    print(f"  update.json -> {version}")


ARCHIVE_SUFFIXES = (".zip", ".7z", ".rar")
ARTIFACT_MANIFEST = "artifact_manifest.json"


def release_notes_from_git(version: str) -> str:
    """Return concise release notes from recent git commits."""
    try:
        import subprocess
        result = subprocess.run(
            ["git", "log", "-5", "--pretty=format:%s"],
            capture_output=True,
            text=True,
            check=True,
        )
        notes = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        if notes:
            return f"Release v{version}\n\n" + "\n".join(f"- {line}" for line in notes)
    except Exception:
        pass
    return f"Release v{version}"


def clean_release_zips(dist_dir: str = "dist", keep: str | None = None) -> list[str]:
    """Remove old top-level release ZIPs from dist."""
    removed = []
    if not os.path.isdir(dist_dir):
        return removed
    keep_name = os.path.basename(keep) if keep else None
    for fname in os.listdir(dist_dir):
        if re.fullmatch(r"MacroForge-v.+\.zip", fname) and fname != keep_name:
            stale = os.path.join(dist_dir, fname)
            try:
                os.remove(stale)
                removed.append(stale)
                print(f"  removed stale release ZIP: {stale}")
            except OSError as exc:
                print(f"  ! could not remove stale release ZIP {stale}: {exc}")
    return removed


def git_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


def write_artifact_manifest(version: str, src_dir: str, zip_name: str) -> str:
    """Write build metadata into the app folder before ZIP creation."""
    manifest = {
        "version": version,
        "commit": git_commit(),
        "build_time_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "build_host": socket.gethostname(),
        "zip_name": os.path.basename(zip_name),
        "zip_sha256": None,
        "zip_sha256_note": "See the adjacent .sha256 sidecar. Embedding a final ZIP digest inside the ZIP would change the digest.",
    }
    path = os.path.join(src_dir, ARTIFACT_MANIFEST)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")
    return path


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_zip_digest(zip_name: str) -> str:
    digest = sha256_file(zip_name)
    sidecar = f"{zip_name}.sha256"
    with open(sidecar, "w", encoding="utf-8") as f:
        f.write(f"{digest}  {os.path.basename(zip_name)}\n")
    return digest


def create_update_zip(version: str, clean_release: bool = True) -> None:
    """Create ZIP of dist/MacroForge for full _internal + exe replacement."""
    src_dir = "dist/MacroForge"
    zip_name = f"dist/MacroForge-v{version}.zip"
    if not os.path.isdir(src_dir):
        print(f"  ! dist/MacroForge not found, skipping ZIP")
        return
    if clean_release:
        clean_release_zips(os.path.dirname(zip_name), keep=zip_name)
    write_artifact_manifest(version, src_dir, zip_name)
    count = 0
    with zipfile.ZipFile(zip_name, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(src_dir):
            for fname in files:
                if fname.lower().endswith(ARCHIVE_SUFFIXES):
                    print(f"  ! skipping nested archive: {os.path.join(root, fname)}")
                    continue
                fpath = os.path.join(root, fname)
                arcname = os.path.relpath(fpath, src_dir)
                zf.write(fpath, arcname)
                count += 1
    digest = write_zip_digest(zip_name)
    print(f"  {zip_name}  ({count} files)")
    print(f"  {zip_name}.sha256  ({digest})")


if __name__ == "__main__":
    clean_release = "--clean-release" in sys.argv[1:]
    ver = get_version()
    if not ver:
        print("ERROR: Could not read version from version.py")
        sys.exit(1)
    print(f"Version: {ver}")
    write_update_json(ver)
    create_update_zip(ver, clean_release=clean_release)
    sys.exit(0)
