@echo off
title VocalPro - Setup
color 0B
echo.
echo  ==============================================
echo     VocalPro v2.5.0 - Setup
echo  ==============================================
echo.

:: -- Check Python ---------------------------------------------------
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

for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo  Found Python %PYVER%

:: -- 1) Create virtual environment ----------------------------------
echo.
echo  [1/4] Creating virtual environment...
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

:: -- 2) Install Python dependencies ---------------------------------
echo.
echo  [2/4] Installing Python dependencies...
call venv\Scripts\activate.bat

if exist api_server\requirements.txt (
    pip install -r api_server\requirements.txt --quiet
    if %errorlevel% neq 0 (
        echo  [ERROR] Failed to install API dependencies.
        pause
        exit /b 1
    )
) else if exist requirements.txt (
    echo         Legacy requirements.txt found - installing...
    pip install -r requirements.txt --quiet
    if %errorlevel% neq 0 (
        echo  [ERROR] Failed to install dependencies.
        pause
        exit /b 1
    )
) else (
    echo  [ERROR] No requirements file found.
    pause
    exit /b 1
)
echo         Python dependencies installed.

:: -- 3) Build Flutter app -------------------------------------------
echo.
echo  [3/4] Building Flutter frontend (if Flutter is installed)...
where flutter >nul 2>&1
if %errorlevel% equ 0 (
    cd flutter_app
    echo         Running flutter build windows --release...
    flutter build windows --release 2>&1
    if %errorlevel% neq 0 (
        echo.
        echo  [WARNING] Flutter build failed.
        echo         Run 'flutter doctor' for help: https://docs.flutter.dev
    ) else (
        echo         Flutter app built successfully!
    )
    cd ..
) else (
    echo         [SKIP] Flutter not found. Install from: https://flutter.dev
    echo         The app requires Flutter to be installed.
)

:: -- 4) Verify FFmpeg -----------------------------------------------
echo.
echo  [4/4] Checking FFmpeg...
ffmpeg -version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  [WARNING] FFmpeg is not installed or not on PATH.
    echo.
    echo  FFmpeg is required for audio processing. Download from:
    echo    https://ffmpeg.org/download.html
    echo.
    echo  After downloading, add the bin folder to your PATH.
    echo  (Search "environment variables" in Windows Start menu)
) else (
    echo         FFmpeg found.
)

echo.
echo  ==============================================
echo     Setup complete!
echo  ==============================================
echo.
echo  To launch VocalPro, double-click run.bat
echo.
pause
