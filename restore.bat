@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0ghd-zh.ps1" -Action Restore
echo.
pause
