@echo off
setlocal EnableDelayedExpansion
title MacroForge — Builder
color 0A

:: Always resolve to the repo root regardless of where this bat is run from
set "SCRIPT_DIR=%~dp0"
set "SRC_FILE=%SCRIPT_DIR%MacroForge.py"

if not exist "%SRC_FILE%" (
    echo  !! Cannot find MacroForge.py !!
    echo  Expected at: %SRC_FILE%
    pause
    exit /b 1
)

pushd "%SCRIPT_DIR%"

:: Read version from version.py
echo.
> _get_ver.py echo import re,sys
>> _get_ver.py echo with open('version.py','r',encoding='utf-8') as f:
>> _get_ver.py echo     m=re.search(r'VERSION\s*=\s*"([^"]+)"',f.read())
>> _get_ver.py echo     sys.stdout.write(m.group(1) if m else '')
python _get_ver.py > _build_ver.txt
del /f /q _get_ver.py >nul 2>&1
for /f "delims=" %%a in (_build_ver.txt) do set "VER=%%a"
del /f /q _build_ver.txt >nul 2>&1
if "%VER%"=="" (
    echo  !! Could not read version from version.py !!
    pause
    exit /b 1
)
echo ============================================
echo   MacroForge -- Build ^& Package
echo ============================================
echo   Version: %VER%
echo   Source:  %CD%
echo.
echo [1/4] Building with PyInstaller...
:: Use --onedir (not --onefile) so the updater can replace the .exe in-place.
:: The .exe sits next to its _internal folder — swapping just the .exe works.
python -m PyInstaller --onedir --windowed --name "MacroForge" --noconfirm --clean ^
    "MacroForge.py" ^
    --hidden-import cv2 ^
    --hidden-import PIL ^
    --hidden-import pyautogui ^
    --hidden-import pynput.keyboard._win32 ^
    --hidden-import pynput.mouse._win32 ^
    --icon="MacroForge.ico"

if %errorlevel% neq 0 (
    echo.
    echo  !! BUILD FAILED -- check errors above !!
    popd
    pause
    exit /b 1
)

echo.
echo [2/4] Cleaning old artifacts...
if exist "dist\MacroForge.update.exe" del /f /q "dist\MacroForge.update.exe" >nul 2>&1
copy /y "MacroForge.png" "dist\MacroForge\MacroForge.png" >nul 2>&1
copy /y "MacroForge.ico" "dist\MacroForge\MacroForge.ico" >nul 2>&1

echo [3/4] Generating update.json and ZIP...
python build_helper.py
if %errorlevel% neq 0 (
    echo   !! build_helper.py failed.
)

echo [4/4] Verifying build...
python -c "import sys,os; sys.path.insert(0,os.path.join(os.getcwd(),'dist','MacroForge','_internal')); from version import VERSION; print('  Built exe version:', VERSION)"
if %errorlevel% neq 0 (
    echo   !! Version verification failed.
)

echo.
echo Build complete.
echo   dist\MacroForge\MacroForge.exe
echo   dist\MacroForge-v%VER%.zip
echo   update.json  (auto-generated for v%VER%)
echo.

:: Optional Inno Setup packaging
where iscc >nul 2>&1
if %errorlevel% == 0 (
    echo   Inno Setup found — building installer...
    iscc "/DMyAppVersion=%VER%" setup.iss
    if %errorlevel% equ 0 (
        echo   installer\MacroForge-Setup.exe ready.
    ) else (
        echo   !! Inno Setup build failed.
    )
) else (
    echo   Inno Setup not found in PATH.
    echo   Skipping installer. Install from: https://jrsoftware.org/isdl.php
)

echo.
echo  ============================================
echo   NEXT STEPS
echo  ============================================
echo   1. Commit ^& push version.py + update.json
echo      git add . ^&^& git commit -m "Release v%VER%" ^&^& git push
echo.
echo   2. Install / Update test machine
echo      installer\MacroForge-Setup.exe
echo.

:: ── Auto-create GitHub release if gh CLI is available ──
where gh >nul 2>&1
if %errorlevel% == 0 (
    echo.
    echo [AUTO] GitHub CLI found — creating release v%VER%...
    gh release create v%VER% --repo xRampageous/MacroForge --title "MacroForge v%VER%" --notes "Release v%VER%" 2>nul
    echo [AUTO] Uploading assets...
    gh release upload v%VER% --repo xRampageous/MacroForge --clobber "dist\MacroForge\MacroForge.exe" "dist\MacroForge-v%VER%.zip"
    if %errorlevel% equ 0 (
        echo [AUTO] Release v%VER% published with assets.
    ) else (
        echo [AUTO] Upload failed — run manually:
        echo   gh release upload v%VER% --repo xRampageous/MacroForge --clobber "dist\MacroForge\MacroForge.exe" "dist\MacroForge-v%VER%.zip"
    )
) else (
    echo.
    echo   gh CLI not found. Install from: https://cli.github.com/
    echo   Then create release manually at:
    echo     https://github.com/xRampageous/MacroForge/releases/new
    echo   Upload both:
    echo     dist\MacroForge\MacroForge.exe
    echo     dist\MacroForge-v%VER%.zip
)

echo.
echo   Done.
popd
:: Use ping instead of timeout to avoid "Input redirection is not supported" error
:: when running from IDE / non-interactive console
ping -n 4 127.0.0.1 >nul 2>&1
