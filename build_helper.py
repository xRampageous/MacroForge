#!/usr/bin/env python3
"""Helper script for build.bat — extracts version and writes update.json."""

import json
import os
import re
import sys


def get_version() -> str:
    with open("version.py", "r", encoding="utf-8") as f:
        m = re.search(r'VERSION\s*=\s*"([^"]+)"', f.read())
    return m.group(1) if m else ""


def write_update_json(version: str) -> None:
    data = {
        "version": version,
        "url": f"https://github.com/xRampageous/MacroForge/releases/download/v{version}/MacroForge.exe",
        "notes": f"Release v{version}",
    }
    with open("update.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"  update.json -> {version}")


if __name__ == "__main__":
    ver = get_version()
    if not ver:
        print("ERROR: Could not read version from version.py")
        sys.exit(1)
    print(f"Version: {ver}")
    write_update_json(ver)
    sys.exit(0)
