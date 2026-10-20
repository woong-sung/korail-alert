@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Python virtual environment was not found.
    echo Run the installation commands in README.md first.
    pause
    exit /b 1
)

if exist "alert.pid" (
    set /p ALERT_PID=<"alert.pid"
    powershell.exe -NoProfile -Command "if (Get-Process -Id !ALERT_PID! -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }"
    if not errorlevel 1 (
        echo Korail alert is already running. PID: !ALERT_PID!
        pause
        exit /b 0
    )
    del /q "alert.pid"
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$python = Join-Path $PWD '.venv\Scripts\python.exe'; $stdout = Join-Path $PWD 'alert.log'; $stderr = Join-Path $PWD 'alert-error.log'; $process = Start-Process -FilePath $python -ArgumentList '-u','alert.py' -WorkingDirectory $PWD -RedirectStandardOutput $stdout -RedirectStandardError $stderr -WindowStyle Hidden -PassThru; Set-Content -LiteralPath (Join-Path $PWD 'alert.pid') -Value $process.Id"

if errorlevel 1 (
    echo [ERROR] Failed to start Korail alert.
    pause
    exit /b 1
)

set /p ALERT_PID=<"alert.pid"
echo Korail alert started in the background. PID: %ALERT_PID%
echo Logs: alert.log and alert-error.log
pause
