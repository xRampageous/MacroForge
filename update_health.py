"""Local update health tracking for diagnostics and support."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MAX_EVENTS = 20


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(os.environ.get("APPDATA", Path(sys.executable).parent)) / "MacroForge"
    return Path(__file__).resolve().parent / "MacroForge"


def health_path() -> Path:
    return _base_dir() / "update_health.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _empty() -> dict[str, Any]:
    return {
        "schema": 1,
        "last_check": None,
        "last_manifest": None,
        "last_download": None,
        "last_extract": None,
        "last_handoff": None,
        "last_dry_run": None,
        "last_startup": None,
        "events": [],
    }


def load(path: Path | None = None) -> dict[str, Any]:
    path = path or health_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {**_empty(), **data}
    except Exception:
        pass
    return _empty()


def save(data: dict[str, Any], path: Path | None = None) -> None:
    path = path or health_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def clear(path: Path | None = None) -> None:
    save(_empty(), path)


def record(event: str, path: Path | None = None, **fields: Any) -> dict[str, Any]:
    data = load(path)
    entry = {"time": _now(), "event": event, **fields}
    data["events"].append(entry)
    data["events"] = data["events"][-MAX_EVENTS:]
    key_map = {
        "check": "last_check",
        "manifest": "last_manifest",
        "download": "last_download",
        "extract": "last_extract",
        "handoff": "last_handoff",
        "dry_run": "last_dry_run",
        "startup": "last_startup",
    }
    for prefix, key in key_map.items():
        if event == prefix or event.startswith(f"{prefix}_"):
            data[key] = entry
            break
    save(data, path)
    return data


def mark_startup(version: str, path: Path | None = None) -> dict[str, Any]:
    data = load(path)
    last = data.get("last_handoff") or {}
    from_version = last.get("from_version")
    to_version = last.get("to_version")
    completed = bool(to_version and to_version == version)
    return record(
        "startup_success" if completed else "startup",
        path,
        version=version,
        updated_from=from_version if completed else None,
        updated_to=to_version if completed else None,
    )


def overall_status(path: Path | None = None) -> str:
    data = load(path)
    startup = data.get("last_startup") or {}
    if startup.get("event") == "startup_success":
        return "Completed"
    for key in ("last_handoff", "last_extract", "last_download", "last_manifest", "last_check", "last_dry_run"):
        item = data.get(key) or {}
        status = str(item.get("status") or "").lower()
        if status in {"failed", "invalid"}:
            return "Failed"
    dry_run = data.get("last_dry_run") or {}
    if str(dry_run.get("status") or "").lower() == "ready":
        return "Ready"
    check = data.get("last_check") or {}
    if str(check.get("status") or "").lower() == "available":
        return "Update Available"
    return "Unknown"


def summary_lines(path: Path | None = None) -> list[str]:
    data = load(path)

    def fmt(label: str, key: str) -> str:
        item = data.get(key) or {}
        if not item:
            return f"Update health {label}: None"
        status = item.get("status") or item.get("event", "unknown")
        version = item.get("remote_version") or item.get("to_version") or item.get("version")
        err = item.get("error")
        suffix = f" · {version}" if version else ""
        if err:
            suffix += f" · {err}"
        return f"Update health {label}: {status}{suffix}"

    return [
        f"Update Health: {overall_status(path)}",
        f"Update health file: {health_path()}",
        fmt("check", "last_check"),
        fmt("manifest", "last_manifest"),
        fmt("download", "last_download"),
        fmt("extract", "last_extract"),
        fmt("handoff", "last_handoff"),
        fmt("dry run", "last_dry_run"),
        fmt("startup", "last_startup"),
    ]
