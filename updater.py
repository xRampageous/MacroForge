"""MacroForge auto-updater.

Checks a remote JSON manifest for a newer version, downloads it, and
performs a self-replace via a detached batch script so the running
process can be safely overwritten on Windows.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from version import VERSION, VERSION_TUPLE, UPDATE_URL

logger = logging.getLogger("macroforge")

MANIFEST_TIMEOUT = 8  # seconds
DOWNLOAD_TIMEOUT = 60  # seconds


def _is_frozen() -> bool:
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def _exe_path() -> Path:
    """Path to the current running executable (or .py script)."""
    if _is_frozen():
        return Path(sys.executable).resolve()
    return Path(__file__).resolve().parent / "MacroForge.py"


def _work_dir() -> Path:
    """Directory where the executable lives (or repo root)."""
    return _exe_path().parent


def check_update(silent: bool = True) -> dict | None:
    """
    Return manifest dict if a newer version is available, else None.
    If UPDATE_URL is empty, silently returns None.
    """
    if not UPDATE_URL.strip():
        return None

    try:
        import time as _time
        cache_bust = f"{_time.time():.0f}"
        req_url = f"{UPDATE_URL}?t={cache_bust}" if "?" not in UPDATE_URL else f"{UPDATE_URL}&t={cache_bust}"
        req = urllib.request.Request(
            req_url,
            headers={"User-Agent": f"MacroForge/{VERSION}"},
        )
        with urllib.request.urlopen(req, timeout=MANIFEST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        if not silent:
            logger.warning(f"Update check failed: {e}")
        return None

    remote_ver = data.get("version", "").strip()
    if not remote_ver:
        return None

    try:
        remote_tuple = tuple(int(p) for p in remote_ver.split(".") if p.isdigit())
    except Exception:
        return None

    if remote_tuple > VERSION_TUPLE:
        logger.info(f"Update available: {VERSION} -> {remote_ver}")
        return data
    return None


def _write_batch_updater(current_exe: Path, new_exe: Path) -> Path:
    """Write a Windows batch script that replaces the exe and relaunches."""
    bat = current_exe.parent / "MacroForge_update.bat"
    bat_content = f"""@echo off
title MacroForge Updater
color 0A
echo Waiting for MacroForge to close...
:waitloop
tasklist | findstr /I "MacroForge.exe" >nul 2>&1
if %errorlevel% == 0 (
    timeout /t 1 /nobreak >nul
    goto waitloop
)
echo Installing update...
timeout /t 1 /nobreak >nul
move /Y "{new_exe}" "{current_exe}" >nul 2>&1
if %errorlevel% neq 0 (
    echo Update failed — permissions error.
    pause
    del "%~f0"
    exit /b 1
)
echo Launching MacroForge...
start "" "{current_exe}"
del "%~f0"
"""
    bat.write_text(bat_content, encoding="ascii")
    return bat


def perform_update(manifest: dict, progress_cb=None) -> bool:
    """
    Download the new exe and spawn a detached batch updater.
    Optional progress_cb(bytes_downloaded, total_bytes) is called periodically.
    Returns True if the hand-off was started (app should exit).
    """
    download_url = manifest.get("url", "").strip()
    if not download_url:
        logger.error("Update manifest missing 'url'")
        return False

    current = _exe_path()
    work = _work_dir()
    new_file = work / "MacroForge.update.exe"

    # Download in chunks with progress
    try:
        logger.info(f"Downloading update from {download_url} ...")
        req = urllib.request.Request(
            download_url,
            headers={"User-Agent": f"MacroForge/{VERSION}"},
        )
        with urllib.request.urlopen(req, timeout=DOWNLOAD_TIMEOUT) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            chunk_size = 64 * 1024
            with open(new_file, "wb") as f:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_cb and total:
                        progress_cb(downloaded, total)
        logger.info(f"Saved to {new_file}")
    except Exception as e:
        logger.error(f"Download failed: {e}")
        return False

    # Write updater batch
    bat = _write_batch_updater(current, new_file)

    # Launch detached — app should exit immediately so the batch can swap files
    try:
        subprocess.Popen(
            [str(bat)],
            creationflags=subprocess.CREATE_NEW_CONSOLE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        logger.info("Updater launched — exiting for replacement.")
        return True
    except Exception as e:
        logger.error(f"Failed to launch updater: {e}")
        return False
