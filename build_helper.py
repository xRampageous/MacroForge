#!/usr/bin/env python3
"""Helper script for build.bat — extracts version, writes update.json, creates ZIP."""

import json
import os
import re
import sys
import zipfile


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
        "zip_url": f"https://github.com/xRampageous/MacroForge/releases/download/v{version}/MacroForge-v{version}.zip",
        "notes": existing_notes,
    }
    with open("update.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    print(f"  update.json -> {version}")


def create_update_zip(version: str) -> None:
    """Create ZIP of dist/MacroForge for full _internal + exe replacement."""
    src_dir = "dist/MacroForge"
    zip_name = f"dist/MacroForge-v{version}.zip"
    if not os.path.isdir(src_dir):
        print(f"  ! dist/MacroForge not found, skipping ZIP")
        return
    count = 0
    with zipfile.ZipFile(zip_name, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(src_dir):
            for fname in files:
                fpath = os.path.join(root, fname)
                arcname = os.path.relpath(fpath, src_dir)
                zf.write(fpath, arcname)
                count += 1
    print(f"  {zip_name}  ({count} files)")


if __name__ == "__main__":
    ver = get_version()
    if not ver:
        print("ERROR: Could not read version from version.py")
        sys.exit(1)
    print(f"Version: {ver}")
    write_update_json(ver)
    create_update_zip(ver)
    sys.exit(0)
