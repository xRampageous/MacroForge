@echo off
setlocal EnableDelayedExpansion
:: MacroForge — Automated Build + Release
:: Usage: release_auto.bat [major|minor|patch|none]
:: Default: patch bump

cd /d "%~dp0"

set "BUMP=%~1"
if "%BUMP%"=="" set "BUMP=patch"

:: ── Bump version ──
if not "%BUMP%"=="none" (
    python bump_version.py %BUMP%
    if %errorlevel% neq 0 (
        echo [ERROR] Version bump failed.
        exit /b 1
    )
)

:: ── Build ──
call build.bat < nul
if %errorlevel% neq 0 (
    echo [ERROR] Build failed.
    exit /b 1
)

:: ── Read version ──
python -c "import re,sys; t=open('version.py','r',encoding='utf-8').read(); m=re.search(r'VERSION\s*=\s*\"([^\"]+)\"',t); sys.stdout.write(m.group(1) if m else '')" > _ver.txt
set /p VER=< _ver.txt
del /f /q _ver.txt >nul 2>&1

if "%VER%"=="" (
    echo [ERROR] Could not read version.
    exit /b 1
)

echo.
echo ============================================
echo   RELEASING v%VER%
echo ============================================

:: ── Delete existing release if present ──
gh release delete v%VER% --repo xRampageous/MacroForge --yes >nul 2>&1

:: ── Create release ──
gh release create v%VER% --repo xRampageous/MacroForge --title "MacroForge v%VER%" --notes "Release v%VER%"
if %errorlevel% neq 0 (
    echo [ERROR] Release creation failed.
    exit /b 1
)

:: ── Upload assets ──
gh release upload v%VER% --repo xRampageous/MacroForge --clobber "dist\MacroForge\MacroForge.exe" "dist\MacroForge-v%VER%.zip"
if %errorlevel% neq 0 (
    echo [ERROR] Asset upload failed.
    exit /b 1
)

:: ── Commit & push update.json + version.py to main so raw URL serves latest manifest ──
echo.
echo [INFO] Pushing update.json to main branch...
git add version.py update.json >nul 2>&1
git commit -m "Release v%VER%" >nul 2>&1
git push origin main >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] Git push failed — update.json may be out of sync on raw URL.
) else (
    echo [OK] update.json synced to main branch.
)

echo.
echo [DONE] Released v%VER% to GitHub.
echo   https://github.com/xRampageous/MacroForge/releases/tag/v%VER%
