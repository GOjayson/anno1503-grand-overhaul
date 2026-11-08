@echo off
cd /d "%~dp0"
set "PYTHONPATH=%~dp0src"
python -B -m anno1503_overhaul gui
if errorlevel 1 pause
