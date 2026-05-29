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

:: Read version from version.py using Python (reliable)
echo.
for /f "delims=" %%a in ('python -c "import re; f=open('version.py','r'); m=re.search(r'VERSION\s*=\s*\"([^\"]+)\"',f.read()); f.close(); print(m.group(1) if m else '')"') do set "VER=%%a"
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

:: Auto-update update.json
echo [0/5] Updating update.json...
python -c "import json,sys; v=sys.argv[1]; data={'version':v,'url':f'https://github.com/xRampageous/MacroForge/releases/download/v{v}/MacroForge.exe','notes':'Release v'+v}; json.dump(data,open('update.json','w'),indent=2); print('  update.json ->',v)" %VER%
if %errorlevel% neq 0 (
    echo   !! Failed to write update.json -- check Python is available.
)

echo.
echo [1/5] Closing any running instance...
taskkill /f /im "MacroForge.exe" >nul 2>&1
timeout /t 1 /nobreak >nul

echo [2/5] Building with PyInstaller...
:: Use --onedir (not --onefile) so the updater can replace the .exe in-place.
:: The .exe sits next to its _internal folder — swapping just the .exe works.
python -m PyInstaller --onedir --windowed --name "MacroForge" --noconfirm ^
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
echo [3/5] Cleaning old artifacts...
if exist "dist\MacroForge.update.exe" del /f /q "dist\MacroForge.update.exe" >nul 2>&1
copy /y "MacroForge.png" "dist\MacroForge\MacroForge.png" >nul 2>&1
copy /y "MacroForge.ico" "dist\MacroForge\MacroForge.ico" >nul 2>&1

echo [4/5] Verifying build...
python -c "import sys,os; sys.path.insert(0,os.path.join(os.getcwd(),'dist','MacroForge','_internal')); from version import VERSION; print('  Built exe version:', VERSION)"
if %errorlevel% neq 0 (
    echo   !! Version verification failed.
)

echo.
echo [5/5] Build complete.
echo   dist\MacroForge\MacroForge.exe
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
echo   2. Create GitHub Release v%VER%
echo      Tag: v%VER%
echo      Upload: dist\MacroForge\MacroForge.exe
echo.
echo   3. Install / Update test machine
echo      installer\MacroForge-Setup.exe
echo.
echo   Done.
popd
timeout /t 3 /nobreak >nul
