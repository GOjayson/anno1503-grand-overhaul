@echo off
setlocal
title Anno 1503 World Settings DEVELOPMENT activation - 0.11.0-dev.1
cd /d "%~dp0"
echo Start Anno 1503 normally through Ubisoft Connect and leave it at the main menu.
echo This requires exact Food 0.5 in the original game and this package installed on its marked copy.
echo All world options are chosen inside the game. Activation lasts until the game closes.
echo Activate in each fresh Anno process before starting a new world or loading a saved world.
echo Do not click game controls while activation runs.
pause
where py >nul 2>&1
if not errorlevel 1 goto use_py
where python >nul 2>&1
if errorlevel 1 goto missing
python -B -u "%~dp0activation\activate_world_settings.py" --install
set "ANNO_WORLD_RESULT=%ERRORLEVEL%"
goto done
:use_py
py -3-64 -B -u "%~dp0activation\activate_world_settings.py" --install
set "ANNO_WORLD_RESULT=%ERRORLEVEL%"
goto done
:missing
echo ERROR: 64-bit Python 3.10 or newer is required.
set "ANNO_WORLD_RESULT=1"
:done
echo.
if "%ANNO_WORLD_RESULT%"=="0" (echo Activated. Start a new endless game to choose World Settings, or load a saved world with its saved AI policy.) else (echo Activation failed. Read the ERROR above; no source game files were installed or restored.)
pause
exit /b %ANNO_WORLD_RESULT%
