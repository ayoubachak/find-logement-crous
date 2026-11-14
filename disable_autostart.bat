@echo off
setlocal
set "SERVICE=FindLogement"
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "LAUNCHER=%STARTUP%\FindLogementNotifier.bat"

:: Ask for administrator rights if needed (a UAC prompt will appear)
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Requesting administrator rights...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

echo Disabling automatic start for the service "%SERVICE%"...
sc config %SERVICE% start= demand
if %errorLevel% neq 0 goto :noservice

echo Stopping the service...
sc stop %SERVICE% >nul 2>&1

echo Removing the desktop helper from startup and stopping it...
if exist "%LAUNCHER%" del "%LAUNCHER%"
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='pythonw.exe'\" | Where-Object { $_.CommandLine -like '*notifier.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"

echo.
sc query %SERVICE% | findstr /i "STATE"
echo.
echo Done. Nothing will start with the computer anymore.
echo You can still start the service manually with:  sc start %SERVICE%
pause
exit /b 0

:noservice
echo.
echo ERROR: service "%SERVICE%" not found. Was it installed with NSSM?
pause
exit /b 1
