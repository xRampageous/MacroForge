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
for /f "tokens=2 delims==" %%a in ('findstr /R "^VERSION = " version.py') do (
    set "RAW_VER=%%a"
    set "VER=!RAW_VER:"=!"
    set "VER=!VER: =!"
)
echo ============================================
echo   MacroForge -- Build ^& Package
echo ============================================
echo   Version: %VER%
echo   Source:  %CD%
echo.

echo [1/4] Closing any running instance...
taskkill /f /im "MacroForge.exe" >nul 2>&1
timeout /t 1 /nobreak >nul

echo [2/4] Building with PyInstaller...
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
echo [3/4] Cleaning old artifacts...
if exist "dist\MacroForge.update.exe" del /f /q "dist\MacroForge.update.exe" >nul 2>&1
copy /y "MacroForge.png" "dist\MacroForge\MacroForge.png" >nul 2>&1
copy /y "MacroForge.ico" "dist\MacroForge\MacroForge.ico" >nul 2>&1

echo [4/4] Build complete.
echo   dist\MacroForge\MacroForge.exe
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
echo  Done.
popd
timeout /t 3 /nobreak >nul
