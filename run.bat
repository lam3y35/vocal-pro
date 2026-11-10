@echo off
title VocalPro v3 -- Studio AI Vocal Separator
color 0B
cd /d "%~dp0"

echo ==============================================================================
echo                      VocalPro v3.0.0 -- Studio Workstation
echo ==============================================================================
echo.

:: 1. Check if release executable exists
if exist "release\vocalpro.exe" (
    echo [INFO] Starting VocalPro Desktop App...
    start "" "release\vocalpro.exe"
    exit /b 0
)

:: 2. If cargo is available, run native Tauri desktop shell
where cargo >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo [INFO] Launching native Tauri v2 desktop application via Cargo...
    npm run tauri dev
    exit /b 0
)

:: 3. Fallback: Launch web dev preview
where npm >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo [INFO] Launching VocalPro Web Studio...
    npm run dev
    exit /b 0
)

echo [ERROR] Neither release\vocalpro.exe nor cargo/npm were found.
echo Please run setup.bat first.
pause
exit /b 1
