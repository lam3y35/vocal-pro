@echo off
title VocalPro - Build Distributable
color 0B
echo.
echo  ========================================
echo    VocalPro - Build Distributable Zip
echo  ========================================
echo.

cd /d "%~dp0"

:: Activate venv
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
) else (
    echo  [ERROR] Virtual environment not found. Run setup.bat first.
    pause
    exit /b 1
)

:: Check PyInstaller
pip show pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    echo  Installing PyInstaller...
    pip install pyinstaller --quiet
)

:: Clean previous build
echo  Cleaning previous builds...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

:: Build with PyInstaller
echo.
echo  Building VocalPro executable...
pyinstaller gui_app.spec --noconfirm
if %errorlevel% neq 0 (
    echo.
    echo  [ERROR] Build failed.
    pause
    exit /b 1
)

:: Create distributable zip
echo.
echo  Creating zip archive...
set ZIPNAME=VocalPro-dist.zip
if exist %ZIPNAME% del %ZIPNAME%

powershell -Command "Compress-Archive -Path 'dist\VocalPro\*' -DestinationPath '%ZIPNAME%'"

echo.
echo  ========================================
echo    Build complete!
echo  ========================================
echo.
echo  Output: %ZIPNAME%
echo  Size:
powershell -Command "(Get-Item '%ZIPNAME%').Length / 1MB" 2>nul
echo  MB
echo.
echo  Users can extract this zip and run VocalPro.exe directly.
echo.
pause
