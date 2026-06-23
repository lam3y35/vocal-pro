@echo off
title VocalPro - Setup
color 0B
echo.
echo  ========================================
echo    VocalPro - One-Click Setup
echo  ========================================
echo.

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERROR] Python is not installed or not on PATH.
    echo.
    echo  Please install Python 3.12+ from:
    echo    https://www.python.org/downloads/
    echo.
    echo  IMPORTANT: Check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

:: Check Python version
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo  Found Python %PYVER%

:: Create virtual environment
echo.
echo  [1/3] Creating virtual environment...
if exist venv (
    echo         venv already exists, skipping.
) else (
    python -m venv venv
    if %errorlevel% neq 0 (
        echo  [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo         Done.
)

:: Activate and install dependencies
echo.
echo  [2/3] Installing dependencies (this may take a few minutes)...
call venv\Scripts\activate.bat
pip install -r requirements.txt --quiet
if %errorlevel% neq 0 (
    echo.
    echo  [ERROR] Failed to install dependencies.
    echo  Check your internet connection and try again.
    pause
    exit /b 1
)
echo         Done.

:: Verify FFmpeg
echo.
echo  [3/3] Checking FFmpeg...
ffmpeg -version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  [WARNING] FFmpeg is not installed or not on PATH.
    echo.
    echo  FFmpeg is required for audio processing. Download it from:
    echo    https://ffmpeg.org/download.html
    echo.
    echo  After downloading, add the bin folder to your system PATH.
    echo  (Search "environment variables" in Windows Start menu)
) else (
    echo         FFmpeg found.
)

echo.
echo  ========================================
echo    Setup complete!
echo  ========================================
echo.
echo  To launch VocalPro, double-click run.bat
echo.
pause
