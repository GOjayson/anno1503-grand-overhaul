@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -File "%~dp0CREATE_SHORTCUT.ps1"
if errorlevel 1 pause
