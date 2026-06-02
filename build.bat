@echo off
setlocal EnableDelayedExpansion
title MacroForge - Builder
color 0A

:: ===========================================================
::  PARSE FLAGS
:: ===========================================================
set "FAST=0"
set "NO_ZIP=0"
set "NO_SMOKE=0"
set "NO_INSTALLER=0"
set "CLEAN_RELEASE=0"

for %%a in (%*) do (
    if "%%~a"=="--fast"     set "FAST=1"
    if "%%~a"=="--no-zip"  set "NO_ZIP=1"
    if "%%~a"=="--no-smoke" set "NO_SMOKE=1"
    if "%%~a"=="--no-installer" set "NO_INSTALLER=1"
    if "%%~a"=="--clean-release" set "CLEAN_RELEASE=1"
)

:: ===========================================================
::  CONFIG
:: ===========================================================
set "SCRIPT_DIR=%~dp0"
set "SRC_FILE=%SCRIPT_DIR%MacroForge.py"
set "SPEC_FILE=%SCRIPT_DIR%MacroForge.spec"
set "ICON_FILE=%SCRIPT_DIR%MacroForge.ico"
set "PNG_FILE=%SCRIPT_DIR%MacroForge.png"
set "DIST_DIR=%SCRIPT_DIR%dist"
set "BUILD_DIR=%SCRIPT_DIR%build"

:: ===========================================================
::  PRE-FLIGHT
:: ===========================================================
if not exist "%SRC_FILE%" (
    echo  [ERROR] Cannot find MacroForge.py
    echo          Expected: %SRC_FILE%
    pause & exit /b 1
)
if not exist "%SPEC_FILE%" (
    echo  [ERROR] Cannot find MacroForge.spec
    echo          Expected: %SPEC_FILE%
    pause & exit /b 1
)

python -c "import PyInstaller" >nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERROR] PyInstaller is not installed. Run: pip install pyinstaller
    pause & exit /b 1
)

cd /d "%SCRIPT_DIR%"

:: ===========================================================
::  READ VERSION
:: ===========================================================
python -c "import re; m=re.search(r'VERSION\s*=\s*\x22([^\x22]+)\x22', open('version.py','r',encoding='utf-8').read()); print(m.group(1) if m else '')" > _ver.txt
for /f "delims=" %%v in (_ver.txt) do set "VER=%%v"
del /f /q _ver.txt >nul 2>&1
if "%VER%"=="" (
    echo  [ERROR] Could not read version from version.py
    pause & exit /b 1
)

echo.
echo  ============================================
echo   MacroForge  Build ^& Package
echo  ============================================
echo   Version  : %VER%
if "%FAST%"=="1"       echo   Mode     : FAST ^(incremental^)
if "%NO_ZIP%"=="1"     echo   ZIP      : skipped
if "%NO_SMOKE%"=="1"  echo   Smoke    : skipped
if "%NO_INSTALLER%"=="1" echo   Installer: skipped
if "%CLEAN_RELEASE%"=="1" echo   Release : cleaning old dist ZIPs
echo.

:: ===========================================================
::  STEP 1 - BUILD  (timed)
:: ===========================================================
echo [1/5] Building with PyInstaller (onedir)...
set "START_TIME=%time%"

if "%FAST%"=="1" (
    echo        Mode: incremental ^(skipping --clean^)
    python -m PyInstaller "%SPEC_FILE%" --noconfirm --distpath "%DIST_DIR%" --workpath "%BUILD_DIR%"
) else (
    python -m PyInstaller "%SPEC_FILE%" --noconfirm --clean --distpath "%DIST_DIR%" --workpath "%BUILD_DIR%"
)

if %errorlevel% neq 0 (
    echo  [ERROR] PyInstaller build failed.
    pause & exit /b 1
)
if not exist "%DIST_DIR%\MacroForge\MacroForge.exe" (
    echo  [ERROR] Expected EXE not found.
    pause & exit /b 1
)
echo        EXE OK  ^|  %DIST_DIR%\MacroForge\MacroForge.exe

:: ===========================================================
::  STEP 2 - COPY ASSETS
:: ===========================================================
echo.
echo [2/5] Copying assets...
if exist "%PNG_FILE%" (
    copy /y "%PNG_FILE%" "%DIST_DIR%\MacroForge\MacroForge.png" >nul
    echo        + MacroForge.png
)
if exist "%ICON_FILE%" (
    copy /y "%ICON_FILE%" "%DIST_DIR%\MacroForge\MacroForge.ico" >nul
    echo        + MacroForge.ico
)

:: ===========================================================
::  STEP 3 - GENERATE update.json / ZIP
:: ===========================================================
if "%NO_ZIP%"=="1" goto :skip_zip

echo.
echo [3/5] Generating update.json and ZIP...
if exist "%SCRIPT_DIR%build_helper.py" (
    if "%CLEAN_RELEASE%"=="1" (
        python "%SCRIPT_DIR%build_helper.py" --clean-release
    ) else (
        python "%SCRIPT_DIR%build_helper.py"
    )
    if %errorlevel% neq 0 (
        echo  [WARNING] build_helper.py exited with errors.
    ) else (
        echo        update.json + ZIP generated.
    )
) else (
    echo  [WARNING] build_helper.py not found - skipping.
)
:skip_zip

:: ===========================================================
::  STEP 4 - VERIFY BUILT EXE
:: ===========================================================
echo.
echo [4/5] Verifying built executable...
python -c "import sys,os; p=os.path.join(r'%DIST_DIR%','MacroForge','_internal'); sys.path.insert(0,p); from version import VERSION; print(VERSION)" > _bver.txt
for /f "delims=" %%v in (_bver.txt) do set "BUILT_VER=%%v"
del /f /q _bver.txt >nul 2>&1
if "%BUILT_VER%"=="" (
    echo  [WARNING] Version import check failed.
) else (
    echo        Built version: %BUILT_VER% ^| OK
)

if "%NO_SMOKE%"=="1" goto :skip_smoke

echo        Smoke-test: launching for 3s...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$p = Start-Process -FilePath '%DIST_DIR%\MacroForge\MacroForge.exe' -PassThru -WindowStyle Hidden; Start-Sleep -Seconds 3; if ($p.HasExited) { exit 1 }; Stop-Process -Id $p.Id -Force; exit 0"
if %errorlevel% neq 0 (
    echo  [ERROR] Smoke-test executable exited unexpectedly.
    pause & exit /b 1
)
echo        Smoke-test complete.
:skip_smoke

:: ===========================================================
::  STEP 5 - OPTIONAL PACKAGING
:: ===========================================================
if "%NO_INSTALLER%"=="1" goto :skip_installer

echo.
echo [5/5] Optional packaging...
where iscc >nul 2>&1
if %errorlevel% == 0 (
    if exist "%SCRIPT_DIR%setup.iss" (
        echo        Inno Setup found - building installer...
        iscc "/DMyAppVersion=%VER%" "%SCRIPT_DIR%setup.iss"
        if %errorlevel% equ 0 (
            echo        installer ready.
        ) else (
            echo  [WARNING] Inno Setup build failed.
        )
    ) else (
        echo        setup.iss not found - skipping.
    )
) else (
    echo        Inno Setup not in PATH - skipping.
)
:skip_installer

:: ===========================================================
::  SUMMARY
:: ===========================================================
echo.
echo  ============================================
echo   BUILD COMPLETE  v%VER%
echo  ============================================
echo   Output:
echo     %DIST_DIR%\MacroForge\MacroForge.exe
if "%NO_ZIP%"=="0" (
echo     %DIST_DIR%\MacroForge-v%VER%.zip
echo     %SCRIPT_DIR%update.json
)
echo.
if "%FAST%"=="1" echo   FAST mode: incremental PyInstaller build saved time.
echo.
exit /b 0
