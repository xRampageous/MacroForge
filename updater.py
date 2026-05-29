"""MacroForge auto-updater.

Checks a remote JSON manifest for a newer version, downloads it, and
performs a self-replace via a detached batch script so the running
process can be safely overwritten on Windows.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from version import VERSION, VERSION_TUPLE, UPDATE_URL
from debugger import logger

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
    logger.info(f"check_update: UPDATE_URL={UPDATE_URL!r}, VERSION={VERSION!r}, TUPLE={VERSION_TUPLE}")
    if not UPDATE_URL.strip():
        logger.warning("check_update: UPDATE_URL is empty — skipping")
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
    logger.info(f"check_update: remote_ver={remote_ver!r}")
    if not remote_ver:
        logger.info("check_update: remote version empty")
        return None

    try:
        remote_tuple = tuple(int(p) for p in remote_ver.split(".") if p.isdigit())
    except Exception:
        logger.info("check_update: failed to parse remote version")
        return None

    logger.info(f"check_update: compare {VERSION_TUPLE} vs {remote_tuple}")
    if remote_tuple > VERSION_TUPLE:
        logger.info(f"Update available: {VERSION} -> {remote_ver}")
        return data
    logger.info(f"check_update: no update ({VERSION} >= {remote_ver})")
    return None


def _write_batch_updater(current_exe: Path, new_exe: Path) -> Path:
    """Write a Windows batch script that replaces the exe and relaunches."""
    bat = current_exe.parent / "MacroForge_update.bat"
    c = str(current_exe)
    n = str(new_exe)
    bat_content = f"""@echo off
title MacroForge Updater
color 0A
echo Waiting for MacroForge to close... >"%~dp0_update.log"
:waitloop
tasklist /FI "IMAGENAME eq MacroForge.exe" 2>nul | find /I "MacroForge.exe" >nul
if %errorlevel% == 0 (
    ping -n 2 127.0.0.1 >nul
    goto waitloop
)
echo Process closed. Installing update... >>"%~dp0_update.log"
if not exist "{n}" (
    echo ERROR: Downloaded file not found: {n} >>"%~dp0_update.log"
    pause
    del "%~f0"
    exit /b 1
)
move /Y "{n}" "{c}" >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Failed to replace exe. Check permissions. >>"%~dp0_update.log"
    pause
    del "%~f0"
    exit /b 1
)
echo Update installed. Launching... >>"%~dp0_update.log"
start "" "{c}"
del "%~f0"
"""
    bat.write_text(bat_content, encoding="utf-8")
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

    logger.info(f"Current exe: {current}")
    logger.info(f"Work dir: {work}")
    logger.info(f"Update file target: {new_file}")

    # Verify we can write to work dir
    try:
        test_file = work / ".write_test"
        test_file.write_text("test")
        test_file.unlink()
    except Exception as e:
        logger.error(f"Cannot write to work directory: {e}")
        return False

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
    if not bat.exists():
        logger.error(f"Updater batch not found: {bat}")
        return False
    logger.info(f"Updater batch written: {bat}")

    # Launch detached — app should exit immediately so the batch can swap files
    try:
        subprocess.Popen(
            ["cmd", "/c", str(bat)],
            creationflags=subprocess.CREATE_NEW_CONSOLE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        logger.info("Updater launched — exiting for replacement.")
        return True
    except Exception as e:
        logger.error(f"Failed to launch updater: {e}")
        return False
