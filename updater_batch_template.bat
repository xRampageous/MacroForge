@echo off
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
where robocopy >nul 2>&1
if %errorlevel% == 0 (
    echo Copying new files with robocopy...
    robocopy "{e}" "{w}" /E /MOVE /NFL /NDL /NJH /NJS >nul 2>&1
) else (
    echo Copying new files with xcopy...
    xcopy /E /I /Y /Q "{e}\*.*" "{w}" >nul 2>&1
)
if %errorlevel% gtr 1 (
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

:: Clean up leftover extract dir and zip
if exist "{e}" rmdir /S /Q "{e}" >nul 2>&1
if exist "{z}" del /F /Q "{z}" >nul 2>&1
if exist "{internal_old}" rmdir /S /Q "{internal_old}" >nul 2>&1

echo Update installed. Launching MacroForge...
start "" "{c}"
del "%~f0"
