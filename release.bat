@echo off
setlocal EnableDelayedExpansion
:: MacroForge - One-shot Build + Release
:: Usage:
::   release.bat                    (patch bump, full build)
::   release.bat --bump none          (no bump, full build)
::   release.bat --bump minor --fast  (minor bump, fast build)
::   release.bat --fast --no-smoke    (fast build, skip smoke test)
::
::  Pass-through flags for build.bat:
::    --fast          skip PyInstaller --clean  (incremental, ~10s vs ~90s)
::    --no-zip        skip ZIP generation
::    --no-smoke      skip smoke test
::    --no-installer  skip Inno Setup
::
cd /d "%~dp0"

:: ===========================================================
::  PARSE ARGS
:: ===========================================================
set "BUMP=patch"
set "BUILD_FLAGS="

:arg_loop
set "ARG=%~1"
if "!ARG!"=="" goto :done_args
if "!ARG!"=="--bump" (
    set "BUMP=%~2"
    shift
    shift
    goto :arg_loop
)
:: Pass everything else to build.bat
set "BUILD_FLAGS=!BUILD_FLAGS! !ARG!"
shift
goto :arg_loop
:done_args

:: ===========================================================
::  PRE-FLIGHT
:: ===========================================================
:: Verify gh CLI
gh auth status >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] GitHub CLI not authenticated.
    echo          Run: gh auth login
    pause & exit /b 1
)

:: Verify git repo
git rev-parse --git-dir >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Not in a git repository.
    pause & exit /b 1
)

:: ===========================================================
::  BUMP VERSION
:: ===========================================================
if not "!BUMP!"=="none" (
    echo [PRE] Bumping version ^(!BUMP!^)...
    python bump_version.py !BUMP!
    if %errorlevel% neq 0 (
        echo [ERROR] Version bump failed.
        pause & exit /b 1
    )
    echo      Version bumped.
)

:: ===========================================================
::  READ VERSION
:: ===========================================================
python -c "import re; m=re.search(r'VERSION\s*=\s*\x22([^\x22]+)\x22', open('version.py','r',encoding='utf-8').read()); print(m.group(1) if m else '')" > _ver.txt
for /f "delims=" %%v in (_ver.txt) do set "VER=%%v"
del /f /q _ver.txt >nul 2>&1

if "!VER!"=="" (
    echo [ERROR] Could not read version.
    pause & exit /b 1
)

echo.
echo  ============================================
echo   RELEASE PIPELINE  v!VER!
echo  ============================================
echo.

:: ===========================================================
::  BUILD
:: ===========================================================
echo [1/3] Building...
echo        Flags: !BUILD_FLAGS!
call build.bat !BUILD_FLAGS!
if %errorlevel% neq 0 (
    echo [ERROR] Build failed.
    pause & exit /b 1
)

:: ===========================================================
::  RELEASE
:: ===========================================================
echo.
echo [2/3] Releasing to GitHub...

:: Delete existing release (idempotent)
gh release delete v!VER! --repo xRampageous/MacroForge --yes >nul 2>&1

:: Create release
gh release create v!VER! --repo xRampageous/MacroForge --title "MacroForge v!VER!" --notes "Release v!VER!" >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Release creation failed.
    pause & exit /b 1
)

:: Upload assets
gh release upload v!VER! --repo xRampageous/MacroForge --clobber "dist\MacroForge-v!VER!.zip" >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Asset upload failed.
    pause & exit /b 1
)

echo        Release v!VER! published.

:: ===========================================================
::  PUSH MANIFEST
:: ===========================================================
echo.
echo [3/3] Pushing update manifest...
git add version.py update.json build.bat release.bat build_helper.py >nul 2>&1
git commit -m "Release v!VER!" >nul 2>&1
git push origin main >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] Git push failed - update.json may be stale.
) else (
    echo        Manifest synced to main.
)

:: ===========================================================
::  DONE
:: ===========================================================
echo.
echo  ============================================
echo   DONE  v!VER!
echo  ============================================
echo   https://github.com/xRampageous/MacroForge/releases/tag/v!VER!
echo.
pause
