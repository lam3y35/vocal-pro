@echo off
setlocal enabledelayedexpansion

echo ==============================================================================
echo VocalPro v3.0.0 -- Turnkey Windows AI Engine & Model Installer
echo ==============================================================================
echo.

set "ENGINE_DIR=%APPDATA%\VocalPro\engine"
set "VENV_DIR=%ENGINE_DIR%\venv"
set "PYTHON_EXE=python"

:: 1. Check for system Python
where py >nul 2>&1
if %ERRORLEVEL% equ 0 (
    set "PYTHON_EXE=py -3"
) else (
    where python >nul 2>&1
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Python 3.10+ was not found on your system.
        echo Please install Python 3.10 or 3.11 from https://www.python.org/downloads/
        echo (Make sure to check "Add Python to PATH" during installation)
        echo.
        pause
        exit /b 1
    )
)

echo [1/4] Found Python runtime: %PYTHON_EXE%
echo [2/4] Initializing isolated AI engine at %VENV_DIR%...
if not exist "%ENGINE_DIR%" mkdir "%ENGINE_DIR%"

if not exist "%VENV_DIR%\Scripts\activate.bat" (
    %PYTHON_EXE% -m venv "%VENV_DIR%"
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"

echo [3/4] Installing PyTorch Demucs & Studio DSP dependencies...
"%VENV_PYTHON%" -m pip install --upgrade pip
"%VENV_PYTHON%" -m pip install torch demucs soundfile numpy scipy librosa mido resampy platformdirs

echo [4/4] Pre-installing and verifying default Demucs AI model weights...
set "PYTHONPATH=%~dp0..\worker"
"%VENV_PYTHON%" -m vocalpro_worker.model_installer htdemucs

echo.
echo ==============================================================================
echo [SUCCESS] VocalPro v3 AI Engine is installed and ready for 100%% offline use!
echo ==============================================================================
echo.
pause
