"""MacroForge auto-updater.

Checks a remote JSON manifest for a newer version, downloads it, and
performs a self-replace via a detached batch script so the running
process can be safely overwritten on Windows.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

from version import VERSION, VERSION_TUPLE, UPDATE_URL
from debugger import logger

MANIFEST_TIMEOUT = 8  # seconds
DOWNLOAD_TIMEOUT = 120  # seconds (ZIPs are larger)


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
        import time as _time, random as _random
        cache_bust = f"{_time.time():.6f}_{_random.randint(100000, 999999)}"
        req_url = f"{UPDATE_URL}?t={cache_bust}" if "?" not in UPDATE_URL else f"{UPDATE_URL}&t={cache_bust}"
        req = urllib.request.Request(
            req_url,
            headers={
                "User-Agent": f"MacroForge/{VERSION}",
                "Cache-Control": "no-cache",
            },
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


def _write_batch_updater(work_dir: Path, current_exe: Path, extract_dir: Path, zip_file: Path) -> Path:
    """Write a Windows batch script that replaces _internal + exe and relaunches."""
    bat = work_dir / "MacroForge_update.bat"
    c = str(current_exe)
    w = str(work_dir)
    e = str(extract_dir)
    z = str(zip_file)
    internal_old = str(work_dir / "_internal.old")
    internal_cur = str(work_dir / "_internal")
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

:: Backup old _internal
if exist "{internal_old}" (
    rmdir /S /Q "{internal_old}" >nul 2>&1
)
if exist "{internal_cur}" (
    move /Y "{internal_cur}" "{internal_old}" >nul 2>&1
)

:: Copy new files from extracted ZIP
xcopy /E /I /Y /Q "{e}\\*" "{w}" >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Failed to copy new files. >>"%~dp0_update.log"
    :: Rollback
    if exist "{internal_old}" (
        rmdir /S /Q "{internal_cur}" >nul 2>&1
        move /Y "{internal_old}" "{internal_cur}" >nul 2>&1
    )
    pause
    del "%~f0"
    exit /b 1
)

:: Clean up
rmdir /S /Q "{e}" >nul 2>&1
del /F /Q "{z}" >nul 2>&1
if exist "{internal_old}" (
    rmdir /S /Q "{internal_old}" >nul 2>&1
)

echo Update installed. Launching... >>"%~dp0_update.log"
start "" "{c}"
del "%~f0"
"""
    bat.write_text(bat_content, encoding="utf-8")
    return bat


def perform_update(manifest: dict, progress_cb=None) -> bool:
    """
    Download the update ZIP, extract it, and spawn a detached batch updater
    that replaces both the .exe and the _internal folder.
    Optional progress_cb(bytes_downloaded, total_bytes) is called periodically.
    Returns True if the hand-off was started (app should exit).
    """
    zip_url = manifest.get("zip_url", "").strip()
    exe_url = manifest.get("url", "").strip()
    download_url = zip_url or exe_url
    if not download_url:
        logger.error("Update manifest missing 'zip_url' or 'url'")
        return False

    current = _exe_path()
    work = _work_dir()
    zip_file = work / "MacroForge.update.zip"
    extract_dir = work / "MacroForge_update_tmp"

    logger.info(f"Current exe: {current}")
    logger.info(f"Work dir: {work}")
    logger.info(f"Update ZIP target: {zip_file}")

    # Verify we can write to work dir
    try:
        test_file = work / ".write_test"
        test_file.write_text("test")
        test_file.unlink()
    except Exception as e:
        logger.error(f"Cannot write to work directory: {e}")
        return False

    # Clean up any leftover temp from previous failed attempts
    if extract_dir.exists():
        try:
            shutil.rmtree(extract_dir)
        except Exception:
            pass
    if zip_file.exists():
        try:
            zip_file.unlink()
        except Exception:
            pass

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
            with open(zip_file, "wb") as f:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_cb and total:
                        progress_cb(downloaded, total)
        logger.info(f"Saved to {zip_file}")
    except Exception as e:
        logger.error(f"Download failed: {e}")
        return False

    # Extract ZIP
    try:
        logger.info(f"Extracting ZIP to {extract_dir} ...")
        with zipfile.ZipFile(zip_file, "r") as zf:
            zf.extractall(extract_dir)
        logger.info("ZIP extracted successfully")
    except Exception as e:
        logger.error(f"ZIP extraction failed: {e}")
        return False

    # Verify extracted exe exists
    extracted_exe = extract_dir / "MacroForge.exe"
    if not extracted_exe.exists():
        logger.error(f"Extracted MacroForge.exe not found in {extract_dir}")
        return False

    # Write updater batch
    bat = _write_batch_updater(work, current, extract_dir, zip_file)
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
