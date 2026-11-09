@echo off
title VocalPro v3
cd /d "%~dp0"

echo ==============================================================================
echo Starting VocalPro v3 -- Studio AI Vocal Separator...
echo ==============================================================================

:: Check if AI engine is ready
if not exist "engine\python.exe" if not exist "engine\Scripts\python.exe" if not exist "%APPDATA%\VocalPro\engine\venv\Scripts\python.exe" (
    where python >nul 2>&1
    if %ERRORLEVEL% neq 0 (
        where py >nul 2>&1
        if %ERRORLEVEL% neq 0 (
            echo.
            echo [Notice] First-time setup: Preparing AI engine...
            echo Downloading and setting up local engine components...
            call ..\scripts\setup_windows_engine.bat
        )
    )
)

start "" "%~dp0vocalpro.exe"
exit /b 0
