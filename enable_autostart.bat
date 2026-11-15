@echo off
setlocal
set "SERVICE=FindLogement"
set "PROJECT=%~dp0"
set "PY=%PROJECT%venv\Scripts\python.exe"
set "PYW=%PROJECT%venv\Scripts\pythonw.exe"
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "LAUNCHER=%STARTUP%\FindLogementNotifier.bat"

:: Ask for administrator rights if needed (a UAC prompt will appear)
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Requesting administrator rights...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

echo Enabling automatic start for the service "%SERVICE%"...
sc config %SERVICE% start= auto
if %errorLevel% neq 0 goto :noservice
sc start %SERVICE% >nul 2>&1

if not exist "%PY%" goto :nohelper

echo Installing the desktop helper library winotify...
"%PY%" -m pip install winotify
if %errorLevel% neq 0 goto :pipfail

echo Making the desktop helper start with Windows...
> "%LAUNCHER%" echo @echo off
>> "%LAUNCHER%" echo start "" "%PYW%" "%PROJECT%notifier.py"

echo Restarting the desktop helper...
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='pythonw.exe'\" | Where-Object { $_.CommandLine -like '*notifier.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
:: explorer starts it with your normal, non-admin rights
explorer.exe "%LAUNCHER%"
goto :done

:noservice
echo.
echo ERROR: service "%SERVICE%" not found. Was it installed with NSSM?
pause
exit /b 1

:nohelper
echo.
echo WARNING: %PY% not found.
echo Keep this file in the project folder, next to the venv folder.
echo The service autostart is enabled, but the desktop helper was not set up.
pause
exit /b 1

:pipfail
echo.
echo ERROR: could not install winotify. The service autostart is enabled, but the desktop helper was not set up.
pause
exit /b 1

:done
echo.
sc query %SERVICE% | findstr /i "STATE"
echo.
echo Done. The service and the desktop helper will start every time you turn on the computer.
echo Choose what happens on new housing at http://127.0.0.1:5000/notify
pause
