@echo off
setlocal
cd /d "%~dp0"

if not exist "alert.pid" (
    echo Korail alert is not running, or alert.pid is missing.
    pause
    exit /b 0
)

set /p ALERT_PID=<"alert.pid"
powershell.exe -NoProfile -Command "$process = Get-Process -Id %ALERT_PID% -ErrorAction SilentlyContinue; if ($process) { Stop-Process -Id $process.Id }"
del /q "alert.pid"
echo Korail alert stopped.
pause
