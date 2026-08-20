@echo off
title VocalPro - Build Distributable
color 0B
setlocal enabledelayedexpansion

echo.
echo  ========================================
echo    VocalPro - Build Distributable
echo    v2.5.0
echo  ========================================
echo.

cd /d "%~dp0"

:: ── 1) Activate virtual environment ──────────────────────────────────────
if not exist venv\Scripts\activate.bat (
    echo  [ERROR] Virtual environment not found. Run setup.bat first.
    pause
    exit /b 1
)
call venv\Scripts\activate.bat

:: ── 2) Run tests ─────────────────────────────────────────────────────────
echo.
echo  [1/4] Running test suite...
python -m pytest tests/unit/ tests/integration/ -m "not slow" --tb=short -q
if %errorlevel% neq 0 (
    echo.
    echo  [ERROR] Tests failed. Aborting build.
    pause
    exit /b 1
)
echo         All tests passed.

:: ── 3) Build Flutter Windows app ─────────────────────────────────────────
echo.
echo  [2/4] Building Flutter Windows app...

where flutter >nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERROR] Flutter SDK not found on PATH.
    echo         Install from: https://docs.flutter.dev/get-started/install/windows
    pause
    exit /b 1
)

cd flutter_app
echo         Running flutter build windows --release...
flutter build windows --release
if %errorlevel% neq 0 (
    echo.
    echo  [ERROR] Flutter build failed.
    echo         Run 'flutter doctor' for diagnostics.
    cd ..
    pause
    exit /b 1
)
cd ..

:: ── 4) Package distributable ─────────────────────────────────────────────
echo.
echo  [3/4] Packaging distributable...

:: Clean previous packaging
if exist dist\VocalPro rmdir /s /q dist\VocalPro

:: Create output directories
mkdir dist\VocalPro 2>nul
mkdir dist\VocalPro\api_server 2>nul

:: Copy Flutter app files
echo         Copying Flutter app...
set RELEASE_DIR=flutter_app\build\windows\x64\runner\Release
copy "%RELEASE_DIR%\vocal_pro_flutter.exe" dist\VocalPro\ >nul
copy "%RELEASE_DIR%\flutter_windows.dll" dist\VocalPro\ >nul
copy "%RELEASE_DIR%\audioplayers_windows_plugin.dll" dist\VocalPro\ >nul
copy "%RELEASE_DIR%\desktop_drop_plugin.dll" dist\VocalPro\ >nul
copy "%RELEASE_DIR%\screen_retriever_windows_plugin.dll" dist\VocalPro\ >nul
copy "%RELEASE_DIR%\tray_manager_plugin.dll" dist\VocalPro\ >nul
copy "%RELEASE_DIR%\window_manager_plugin.dll" dist\VocalPro\ >nul
copy "%RELEASE_DIR%\vocalpro.ico" dist\VocalPro\ >nul
copy "%RELEASE_DIR%\native_assets.json" dist\VocalPro\ >nul

:: Copy Flutter data directory
xcopy /E /I /Q "%RELEASE_DIR%\data" dist\VocalPro\data >nul

:: Copy Python API server
echo         Copying Python API server...
xcopy /E /I /Q api_server dist\VocalPro\api_server >nul

:: Calculate size
for /f "delims=" %%s in ('powershell -NoProfile -Command "[math]::Round((Get-ChildItem 'dist\VocalPro' -Recurse | Measure-Object Length -Sum).Sum / 1MB, 1)"') do set DIST_SIZE=%%s
echo         Package size: !DIST_SIZE! MB

:: ── 5) Create ZIP archive ────────────────────────────────────────────────
echo.
echo  [4/4] Creating distributable ZIP archive...
set ZIPNAME=VocalPro-dist.zip
if exist %ZIPNAME% del %ZIPNAME%

powershell -NoProfile -Command "Compress-Archive -Path 'dist\VocalPro\*' -DestinationPath '%ZIPNAME%'"
if %errorlevel% neq 0 (
    echo  [ERROR] Failed to create ZIP.
    pause
    exit /b 1
)

for /f "delims=" %%s in ('powershell -NoProfile -Command "[math]::Round((Get-Item '%ZIPNAME%').Length / 1MB, 1)"') do set ZIP_SIZE=%%s

echo.
echo  ========================================
echo    Build complete!
echo  ========================================
echo.
echo  Flutter app: dist\VocalPro\vocal_pro_flutter.exe
echo  ZIP archive: %ZIPNAME% (!ZIP_SIZE! MB)
echo.
echo  Users can extract the zip and run VocalPro.exe directly,
echo  or run setup.bat to install the full stack with the API server.
echo.
pause
