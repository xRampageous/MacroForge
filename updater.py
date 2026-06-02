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

MANIFEST_TIMEOUT = 3  # seconds
DOWNLOAD_TIMEOUT = 120  # seconds (ZIPs are larger)


def parse_version_tuple(version: str) -> tuple[int, ...]:
    """Parse strict dotted numeric versions like 3.1.2."""
    value = str(version or "").strip()
    if not value:
        raise ValueError("version is missing")
    parts = value.split(".")
    if not all(part.isdigit() for part in parts):
        raise ValueError(f"invalid version: {version!r}")
    return tuple(int(part) for part in parts)


def validate_manifest(manifest: dict, require_notes: bool = True) -> list[str]:
    """Return manifest validation errors."""
    errors = []
    if not isinstance(manifest, dict):
        return ["manifest must be a JSON object"]
    try:
        parse_version_tuple(manifest.get("version", ""))
    except ValueError as exc:
        errors.append(str(exc))
    if not str(manifest.get("zip_url", "")).strip() and not str(manifest.get("url", "")).strip():
        errors.append("manifest must include zip_url or url")
    if require_notes and not str(manifest.get("notes", "")).strip():
        errors.append("manifest notes must not be empty")
    return errors


def _safe_extract_zip(zf: zipfile.ZipFile, extract_dir: Path) -> None:
    """Extract a ZIP after rejecting paths that escape extract_dir."""
    target_root = extract_dir.resolve()
    for info in zf.infolist():
        name = info.filename.replace("\\", "/")
        if name.startswith("/") or name.startswith("../") or "/../" in name:
            raise ValueError(f"unsafe ZIP member path: {info.filename}")
        target = (target_root / name).resolve()
        if target != target_root and target_root not in target.parents:
            raise ValueError(f"unsafe ZIP member path: {info.filename}")
    zf.extractall(extract_dir)


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
    Returns None on error and sets _last_error for UI display.
    """
    global _last_error
    _last_error = None

    logger.info(f"check_update: UPDATE_URL={UPDATE_URL!r}, VERSION={VERSION!r}, TUPLE={VERSION_TUPLE}")
    if not UPDATE_URL.strip():
        logger.warning("check_update: UPDATE_URL is empty — skipping")
        return None

    try:
        import time as _time, random as _random
        cache_bust = f"{_time.time():.6f}_{_random.randint(100000, 999999)}"
        req_url = f"{UPDATE_URL}?t={cache_bust}" if "?" not in UPDATE_URL else f"{UPDATE_URL}&t={cache_bust}"
        logger.info(f"check_update: fetching {req_url}")
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
        _last_error = str(e)
        logger.error(f"check_update: request failed: {e}")
        if not silent:
            # Raise so the UI can display the error
            raise
        return None

    errors = validate_manifest(data, require_notes=True)
    if errors:
        _last_error = "; ".join(errors)
        logger.error(f"check_update: invalid manifest: {_last_error}")
        if not silent:
            raise ValueError(_last_error)
        return None

    remote_ver = data.get("version", "").strip()
    logger.info(f"check_update: remote_ver={remote_ver!r}")
    if not remote_ver:
        logger.info("check_update: remote version empty")
        return None

    try:
        remote_tuple = parse_version_tuple(remote_ver)
    except Exception as e:
        _last_error = f"Failed to parse version '{remote_ver}': {e}"
        logger.error(f"check_update: {e}")
        if not silent:
            raise
        return None

    logger.info(f"check_update: compare {VERSION_TUPLE} vs {remote_tuple}")
    if remote_tuple > VERSION_TUPLE:
        logger.info(f"Update available: {VERSION} -> {remote_ver}")
        return data
    logger.info(f"check_update: no update ({VERSION} >= {remote_ver})")
    return None


_last_error = None


def get_last_update_error() -> str:
    """Return the last error from check_update, or None."""
    return _last_error


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
echo Waiting for MacroForge to close...
:waitloop
tasklist /FI "IMAGENAME eq MacroForge.exe" 2>nul | find /I "MacroForge.exe" >nul
if %errorlevel% == 0 (
    ping -n 2 127.0.0.1 >nul
    goto waitloop
)
echo Process closed. Waiting for file locks to release...
ping -n 4 127.0.0.1 >nul

:: Remove stale backup if it exists
if exist "{internal_old}" (
    rmdir /S /Q "{internal_old}" >nul 2>&1
)

:: Rename old _internal to backup (retry if locked)
set retries=0
:retry_move
if exist "{internal_cur}" (
    move /Y "{internal_cur}" "{internal_old}" >nul 2>&1
    if %errorlevel% neq 0 (
        set /a retries+=1
        if %retries% lss 5 (
            echo   _internal folder locked, retrying...
            ping -n 3 127.0.0.1 >nul
            goto retry_move
        ) else (
            echo WARNING: Could not rename _internal, copying over instead...
        )
    )
)

:: Use robocopy if available (more reliable), fallback to xcopy
set COPY_OK=0
where robocopy >nul 2>&1
if %errorlevel% == 0 (
    echo Copying new files with robocopy...
    robocopy "{e}" "{w}" /E /NFL /NDL /NJH /NJS >nul 2>&1
    :: robocopy exit codes: 0-7 = success or warnings, 8+ = error
    if %errorlevel% lss 8 set COPY_OK=1
) else (
    echo Copying new files with xcopy...
    xcopy /E /I /Y /Q "{e}\\*" "{w}" >nul 2>&1
    if %errorlevel% == 0 set COPY_OK=1
    if %errorlevel% == 1 set COPY_OK=1
)
if %COPY_OK% == 0 (
    echo ERROR: Failed to copy new files. Exit code: %errorlevel%
    :: Rollback
    if exist "{internal_old}" (
        if exist "{internal_cur}" rmdir /S /Q "{internal_cur}" >nul 2>&1
        move /Y "{internal_old}" "{internal_cur}" >nul 2>&1
    )
    pause
    del "%~f0"
    exit /b 1
)

:: Verify the new exe exists
if not exist "{c}" (
    echo ERROR: MacroForge.exe missing after update!
    pause
    del "%~f0"
    exit /b 1
)

:: Verify _internal folder exists
if not exist "{internal_cur}" (
    echo ERROR: _internal folder missing after update!
    pause
    del "%~f0"
    exit /b 1
)

:: Clean up leftover extract dir and zip
if exist "{e}" rmdir /S /Q "{e}" >nul 2>&1
if exist "{z}" del /F /Q "{z}" >nul 2>&1
if exist "{internal_old}" rmdir /S /Q "{internal_old}" >nul 2>&1

echo Update installed. Launching MacroForge...
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
    errors = validate_manifest(manifest, require_notes=False)
    if errors:
        logger.error("Invalid update manifest: " + "; ".join(errors))
        return False

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
                    if progress_cb:
                        progress_cb(downloaded, total or 0)
        logger.info(f"Saved to {zip_file}")
    except Exception as e:
        logger.error(f"Download failed: {e}")
        return False

    # Extract ZIP
    try:
        logger.info(f"Extracting ZIP to {extract_dir} ...")
        with zipfile.ZipFile(zip_file, "r") as zf:
            _safe_extract_zip(zf, extract_dir)
        logger.info("ZIP extracted successfully")
    except Exception as e:
        logger.error(f"ZIP extraction failed: {e}")
        return False

    # Verify extracted exe exists (handle both flat and subfolder layouts)
    extracted_exe = extract_dir / "MacroForge.exe"
    if not extracted_exe.exists():
        # PyInstaller onedir builds zip the MacroForge/ folder
        extracted_exe = extract_dir / "MacroForge" / "MacroForge.exe"
        if not extracted_exe.exists():
            logger.error(f"Extracted MacroForge.exe not found in {extract_dir}")
            return False
        # Flatten: move contents of subfolder up to extract_dir root
        subdir = extract_dir / "MacroForge"
        for item in subdir.iterdir():
            dest = extract_dir / item.name
            if dest.exists():
                if dest.is_dir():
                    shutil.rmtree(dest)
                else:
                    dest.unlink()
            shutil.move(str(item), str(dest))
        shutil.rmtree(subdir)
        extracted_exe = extract_dir / "MacroForge.exe"

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
        )
        logger.info("Updater launched — exiting for replacement.")
        return True
    except Exception as e:
        logger.error(f"Failed to launch updater: {e}")
        return False
