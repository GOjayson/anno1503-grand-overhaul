@echo off
setlocal
title Anno 1503 Combined Food Mod
cd /d "%~dp0"
set "ANNOFOOD_ACTION=%~1"
if /i "%~1"=="check" goto find_python
if /i "%~1"=="install" goto find_python
if /i "%~1"=="restore" goto find_python
echo Open INSTALL.cmd, CHECK.cmd or RESTORE.cmd.
goto failed
:find_python
where py >nul 2>&1
if not errorlevel 1 goto use_py
where python >nul 2>&1
if not errorlevel 1 goto use_python
echo ERROR: Python 3.10 or newer is required. See README.txt.
goto failed
:use_py
py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if errorlevel 1 goto old_python
py -3 -u "%~dp0food_mod.py" %ANNOFOOD_ACTION% --game-dir "%~dp0.."
set "ANNOFOOD_RESULT=%ERRORLEVEL%"
goto done
:use_python
python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if errorlevel 1 goto old_python
python -u "%~dp0food_mod.py" %ANNOFOOD_ACTION% --game-dir "%~dp0.."
set "ANNOFOOD_RESULT=%ERRORLEVEL%"
goto done
:old_python
echo ERROR: A working Python 3.10 or newer installation was not found.
:failed
set "ANNOFOOD_RESULT=1"
:done
echo.
if "%ANNOFOOD_RESULT%"=="0" (echo Finished successfully.) else (echo Operation failed. Copy the ERROR line above when reporting the problem.)
echo.
pause
exit /b %ANNOFOOD_RESULT%
