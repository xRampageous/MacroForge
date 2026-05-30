@echo off
setlocal EnableDelayedExpansion
title MacroForge — Builder
color 0A

:: ═══════════════════════════════════════════════════════════
::  CONFIG
:: ═══════════════════════════════════════════════════════════
set "SCRIPT_DIR=%~dp0"
set "SRC_FILE=%SCRIPT_DIR%MacroForge.py"
set "SPEC_FILE=%SCRIPT_DIR%MacroForge.spec"
set "ICON_FILE=%SCRIPT_DIR%MacroForge.ico"
set "PNG_FILE=%SCRIPT_DIR%MacroForge.png"
set "VER_FILE=%SCRIPT_DIR%version.py"
set "DIST_DIR=%SCRIPT_DIR%dist"
set "BUILD_DIR=%SCRIPT_DIR%build"

:: ═══════════════════════════════════════════════════════════
::  PRE-FLIGHT CHECKS
:: ═══════════════════════════════════════════════════════════
if not exist "%SRC_FILE%" (
    echo  [ERROR] Cannot find MacroForge.py
    echo          Expected: %SRC_FILE%
    pause
    exit /b 1
)

if not exist "%SPEC_FILE%" (
    echo  [ERROR] Cannot find MacroForge.spec
    echo          Expected: %SPEC_FILE%
    pause
    exit /b 1
)

if not exist "%ICON_FILE%" (
    echo  [WARNING] MacroForge.ico not found — build will use default icon.
)

if not exist "%PNG_FILE%" (
    echo  [WARNING] MacroForge.png not found.
)

:: Verify PyInstaller
python -c "import PyInstaller" >nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERROR] PyInstaller is not installed.
    echo          Run: pip install pyinstaller
    pause
    exit /b 1
)

:: ═══════════════════════════════════════════════════════════
::  READ VERSION
:: ═══════════════════════════════════════════════════════════
pushd "%SCRIPT_DIR%"

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
    echo  [ERROR] Could not read version from version.py
    pause
    popd
    exit /b 1
)

echo ============================================
echo   MacroForge  Build ^& Package
echo ============================================
echo   Version : %VER%
echo   Source  : %CD%
echo   Dist    : %DIST_DIR%
echo.

:: ═══════════════════════════════════════════════════════════
::  STEP 1 — BUILD
:: ═══════════════════════════════════════════════════════════
echo [1/5] Building with PyInstaller (onedir)...
echo        Spec  : %SPEC_FILE%
echo        Dist   : %DIST_DIR%
echo        Build  : %BUILD_DIR%
echo.
python -m PyInstaller "%SPEC_FILE%" --noconfirm --clean --distpath "%DIST_DIR%" --workpath "%BUILD_DIR%"

if %errorlevel% neq 0 (
    echo.
    echo  [ERROR] PyInstaller build failed. Check output above.
    popd
    pause
    exit /b 1
)

:: Verify EXE was produced
if not exist "%DIST_DIR%\MacroForge\MacroForge.exe" (
    echo.
    echo  [ERROR] Expected EXE not found:
    echo          %DIST_DIR%\MacroForge\MacroForge.exe
    popd
    pause
    exit /b 1
)
echo        EXE OK: %DIST_DIR%\MacroForge\MacroForge.exe

:: ═══════════════════════════════════════════════════════════
::  STEP 2 — COPY ASSETS
:: ═══════════════════════════════════════════════════════════
echo.
echo [2/5] Copying assets into dist...
if exist "%PNG_FILE%" (
    copy /y "%PNG_FILE%" "%DIST_DIR%\MacroForge\MacroForge.png" >nul
    echo        + MacroForge.png
) else (
    echo        - MacroForge.png missing, skipped.
)
if exist "%ICON_FILE%" (
    copy /y "%ICON_FILE%" "%DIST_DIR%\MacroForge\MacroForge.ico" >nul
    echo        + MacroForge.ico
) else (
    echo        - MacroForge.ico missing, skipped.
)

:: ═══════════════════════════════════════════════════════════
::  STEP 3 — GENERATE update.json / ZIP
:: ═══════════════════════════════════════════════════════════
echo.
echo [3/5] Generating update.json and ZIP package...
if exist "%SCRIPT_DIR%build_helper.py" (
    python "%SCRIPT_DIR%build_helper.py"
    if %errorlevel% neq 0 (
        echo  [WARNING] build_helper.py exited with errors.
    ) else (
        echo        update.json + ZIP generated.
    )
) else (
    echo  [WARNING] build_helper.py not found — skipping update.json / ZIP.
    echo            Package manually or create build_helper.py
)

:: ═══════════════════════════════════════════════════════════
::  STEP 4 — VERIFY BUILT EXE
:: ═══════════════════════════════════════════════════════════
echo.
echo [4/5] Verifying built executable...
python -c "import sys,os; p=os.path.join(r'%DIST_DIR%','MacroForge','_internal'); sys.path.insert(0,p); from version import VERSION; print('        Built version:', VERSION)"
if %errorlevel% neq 0 (
    echo  [WARNING] Version import check failed.
) else (
    echo        Version import OK.
)

:: Smoke-test: run exe for 3 seconds
echo        Smoke-test: launching MacroForge.exe for 3s...
start "" /B "%DIST_DIR%\MacroForge\MacroForge.exe"
:: wait 3 seconds
ping -n 4 127.0.0.1 >nul 2>&1
:: kill if still running
taskkill /F /IM MacroForge.exe >nul 2>&1
echo        Smoke-test complete.

:: ═══════════════════════════════════════════════════════════
::  STEP 5 — OPTIONAL PACKAGING
:: ═══════════════════════════════════════════════════════════
echo.
echo [5/5] Optional packaging...

:: Inno Setup
where iscc >nul 2>&1
if %errorlevel% == 0 (
    if exist "%SCRIPT_DIR%setup.iss" (
        echo        Inno Setup found — building installer...
        iscc "/DMyAppVersion=%VER%" "%SCRIPT_DIR%setup.iss"
        if %errorlevel% equ 0 (
            echo        installer\MacroForge-Setup.exe ready.
        ) else (
            echo  [WARNING] Inno Setup build failed.
        )
    ) else (
        echo        setup.iss not found — skipping installer.
    )
) else (
    echo        Inno Setup not in PATH — skipping installer.
)

:: ═══════════════════════════════════════════════════════════
::  SUMMARY
:: ═══════════════════════════════════════════════════════════
echo.
echo  ============================================
echo   BUILD COMPLETE  v%VER%
echo  ============================================
echo   Output:
echo     %DIST_DIR%\MacroForge\MacroForge.exe
echo     %DIST_DIR%\MacroForge-v%VER%.zip   (if build_helper ran)
echo     %SCRIPT_DIR%update.json             (if build_helper ran)
echo.

:: GitHub CLI release
where gh >nul 2>&1
if %errorlevel% == 0 (
    echo  [AUTO] GitHub CLI detected.
    set /p PUSH="  Create GitHub release v%VER%? (y/n): "
    if /I "!PUSH!"=="y" (
        gh release create v%VER% --repo xRampageous/MacroForge --title "MacroForge v%VER%" --notes "Release v%VER%" 2>nul
        gh release upload v%VER% --repo xRampageous/MacroForge --clobber "%DIST_DIR%\MacroForge\MacroForge.exe" "%DIST_DIR%\MacroForge-v%VER%.zip" 2>nul
        if %errorlevel% equ 0 (
            echo  [AUTO] Release v%VER% published.
        ) else (
            echo  [AUTO] Upload failed.
        )
    ) else (
        echo  Skipped.
    )
) else (
    echo  GitHub CLI not found.
    echo    Install:  https://cli.github.com/
    echo    Manual:   https://github.com/xRampageous/MacroForge/releases/new
)

echo.
echo   Done.
popd
ping -n 3 127.0.0.1 >nul 2>&1
