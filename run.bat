@echo off
title VocalPro
cd /d "%~dp0"

:: Activate virtual environment
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
) else (
    echo  [ERROR] Virtual environment not found. Run setup.bat first.
    pause
    exit /b 1
)

:: Launch the app
python code\gui_app.py
if %errorlevel% neq 0 (
    echo.
    echo  [ERROR] VocalPro exited with an error.
    pause
)
