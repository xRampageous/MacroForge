"""Support bundle export helpers."""
from __future__ import annotations

import json
import zipfile
from datetime import datetime
from pathlib import Path

import update_health
from debugger import get_log_path
from version import VERSION, UPDATE_URL


def default_bundle_path(base_dir: str | Path | None = None) -> Path:
    base = Path(base_dir) if base_dir else Path.cwd()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return base / f"MacroForge-support-{VERSION}-{stamp}.zip"


def create_support_bundle(
    path: str | Path,
    diagnostics_lines: list[str],
    profile_info: dict | None = None,
    active_profile_path: str | Path | None = None,
) -> Path:
    """Create a ZIP with diagnostics, update health, and log/profile context."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    profile_info = profile_info or {}
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("diagnostics.txt", "\n".join(diagnostics_lines) + "\n")
        zf.writestr(
            "version.json",
            json.dumps({"version": VERSION, "update_url": UPDATE_URL, **profile_info}, indent=2) + "\n",
        )
        health_file = update_health.health_path()
        if health_file.exists():
            zf.write(health_file, "update_health.json")
        else:
            zf.writestr("update_health.json", json.dumps(update_health.load(), indent=2) + "\n")
        log_path = Path(get_log_path())
        if log_path.exists():
            zf.write(log_path, "debug.log")
        if active_profile_path:
            profile_path = Path(active_profile_path)
            if profile_path.exists():
                zf.write(profile_path, f"profiles/{profile_path.name}")
    return target
