@echo off
title VocalPro Console
color 0B
cd /d "%~dp0"

echo.
echo  ==============================================
echo     VocalPro v2.5.0
echo  ==============================================
echo.

:: -- 1) Activate virtual environment --------------------------------
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
) else (
    echo  [ERROR] Virtual environment not found. Run setup.bat first.
    pause
    exit /b 1
)

:: -- 2) Check if server is already running --------------------------
>nul 2>&1 python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=1)"
if %errorlevel% equ 0 (
    echo  [INFO] API server is already running on port 8000.
    set SERVER_PID=0
    goto :launch_flutter
)

:: -- 3) Check dependencies ------------------------------------------
python -c "import fastapi" 2>nul
if %errorlevel% neq 0 (
    echo  [SETUP] Installing Python API dependencies...
    pip install -r api_server\requirements.txt --quiet
)

:: -- 4) Start API server in background ------------------------------
echo  [1/2] Starting AI separation engine on http://127.0.0.1:8000 ...

:: Start server via Python subprocess (captures PID, redirects output to log file)
set SERVER_LOG=%TEMP%\vocalpro_server.log
:: Start server with DETACHED_PROCESS (0x8) to prevent Fortran DLL
:: crash when the console window is minimized or closed.
:: Without this flag, NumPy/SciPy/LAPACK Fortran DLLs crash with
:: "forrtl: error (200): program aborting due to window-CLOSE event".
for /f %%p in ('python -c "import subprocess, os, sys; log=open(os.path.join(os.environ['TEMP'], 'vocalpro_server.log'), 'w'); p=subprocess.Popen([sys.executable, 'api_server/main.py'], stdout=log, stderr=log, creationflags=subprocess.DETACHED_PROCESS, cwd=os.getcwd()); print(p.pid)" 2^>nul') do set SERVER_PID=%%p
if not defined SERVER_PID set SERVER_PID=0
echo         Server PID: %SERVER_PID%

:: Wait for server to be ready
echo         Waiting for server to initialize...
setlocal enabledelayedexpansion
set WAIT_COUNT=0
:wait_loop
if !WAIT_COUNT! GEQ 20 (
    echo  [ERROR] API server failed to start.
    echo         Check log: %SERVER_LOG%
    echo.
    type "%SERVER_LOG%" 2>nul
    pause
    exit /b 1
)
>nul 2>&1 python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=1)" && goto :server_ready
timeout /t 1 /nobreak >nul
set /a WAIT_COUNT+=1
goto :wait_loop
:server_ready
echo         Server is ready!
echo.

:: -- 5) Launch Flutter app ------------------------------------------
:launch_flutter
echo  [2/2] Starting VocalPro Flutter frontend...
echo.

if exist "flutter_app\build\windows\x64\runner\Release\vocal_pro_flutter.exe" (
    start "" "flutter_app\build\windows\x64\runner\Release\vocal_pro_flutter.exe"
    goto :launched
)

if exist "flutter_app\build\windows\x64\runner\Debug\vocal_pro_flutter.exe" (
    start "" "flutter_app\build\windows\x64\runner\Debug\vocal_pro_flutter.exe"
    goto :launched
)

:: Fall back to flutter run
where flutter >nul 2>&1
if %errorlevel% equ 0 (
    echo         Launching via Flutter SDK...
    cd flutter_app
    start "" cmd /c "C:\src\flutter\bin\flutter.bat run -d windows"
    cd ..
    goto :launched
)

echo  [WARNING] Could not find Flutter executable.
echo         The API server is running on http://127.0.0.1:8000
echo         Build the Flutter app first with: flutter build windows
echo.
pause
exit /b 0

:launched
echo.
echo  ==============================================
echo     VocalPro is running!
echo  ==============================================
echo.
echo  API Server:   http://127.0.0.1:8000
echo  App Window:   VocalPro Flutter Frontend
echo.
echo  The console window will now minimize to the taskbar.
echo  Right-click the VocalPro tray icon and select Quit to stop.
echo.

:: Give the Flutter app a moment to fully initialize
timeout /t 2 /nobreak >nul

:: Minimize the console window using VBScript (more reliable than PowerShell)
:: The window title is "VocalPro" (set at the top of this script)
echo Set WshShell = CreateObject("WScript.Shell") > "%TEMP%\vp_minimize.vbs"
echo WshShell.AppActivate "VocalPro Console" >> "%TEMP%\vp_minimize.vbs"
echo WshShell.SendKeys "%% n" >> "%TEMP%\vp_minimize.vbs"
cscript //nologo "%TEMP%\vp_minimize.vbs" >nul 2>&1
del "%TEMP%\vp_minimize.vbs" 2>nul

:: Watch loop — wait for Flutter app to close, then auto-cleanup
:watch_loop
timeout /t 3 /nobreak >nul
tasklist /NH /FI "IMAGENAME eq vocal_pro_flutter.exe" 2>nul | findstr /i "vocal_pro_flutter" >nul
if not errorlevel 1 goto :watch_loop

:: Flutter app closed — restore console and clean up
echo.
echo  VocalPro app closed. Stopping server...

:: Restore console window so user can see the shutdown message
:: (simple PowerShell to restore via system menu)
echo Set WshShell = CreateObject("WScript.Shell") > "%TEMP%\vp_restore.vbs"
echo WshShell.AppActivate "VocalPro Console" >> "%TEMP%\vp_restore.vbs"
echo WshShell.SendKeys "%% r" >> "%TEMP%\vp_restore.vbs"
cscript //nologo "%TEMP%\vp_restore.vbs" >nul 2>&1
del "%TEMP%\vp_restore.vbs" 2>nul

:: Cleanup -- kill only the specific server process (not all Python!)
if defined SERVER_PID if "%SERVER_PID%" NEQ "0" (
    taskkill /F /PID %SERVER_PID% >nul 2>&1
) else if not defined SERVER_PID (
    :: Fallback: find & kill only the api_server python process
    powershell -NoProfile -Command "Get-WmiObject Win32_Process -Filter \"CommandLine like '%%api_server\\main.py%%'\" | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>&1
)
echo  Server stopped. You may close this window.
timeout /t 3 /nobreak >nul

