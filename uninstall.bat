@echo off
title VocalPro - Uninstall
color 0C
echo.
echo  ==============================================
echo     VocalPro v2.5.0 - Uninstall
echo  ==============================================
echo.
echo  This will remove:
echo    - Desktop shortcut (VocalPro.lnk)
echo    - Python virtual environment (venv/)
echo    - Upload cache (%APPDATA%\VocalPro\uploads\)
echo.
echo  Your output files, config, and history will NOT be deleted.
echo.

set /p CONFIRM="Are you sure? (Y/N): "
if /i not "%CONFIRM%"=="Y" (
    echo  Cancelled.
    pause
    exit /b 0
)

:: -- 1) Remove desktop shortcut -------------------------------------
echo.
echo  [1/3] Removing desktop shortcut...
set DESKTOP_PATH=%USERPROFILE%\Desktop
if exist "%DESKTOP_PATH%\VocalPro.lnk" (
    del "%DESKTOP_PATH%\VocalPro.lnk"
    echo         Deleted: %DESKTOP_PATH%\VocalPro.lnk
) else (
    echo         Not found, skipping.
)

:: -- 2) Remove Python virtual environment ----------------------------
echo.
echo  [2/3] Removing virtual environment (venv/)...
if exist venv (
    rmdir /s /q venv
    if %errorlevel% equ 0 (
        echo         Deleted: venv\
    ) else (
        echo         [WARNING] Could not fully delete venv.
        echo         Try closing any running Python processes first.
    )
) else (
    echo         Not found, skipping.
)

:: -- 3) Remove upload cache -----------------------------------------
echo.
echo  [3/3] Removing upload cache...
set UPLOAD_DIR=%APPDATA%\VocalPro\uploads
if exist "%UPLOAD_DIR%" (
    rmdir /s /q "%UPLOAD_DIR%" 2>nul
    echo         Deleted: %UPLOAD_DIR%
) else (
    echo         Not found, skipping.
)

echo.
echo  ==============================================
echo     Uninstall complete!
echo  ==============================================
echo.
echo  What was kept:
echo    - Output files (output_vocals/)
echo    - Config and history (%APPDATA%\VocalPro\)
echo    - Source code and project files
echo.
echo  To fully remove VocalPro, delete this entire folder.
echo.
pause
