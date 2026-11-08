@echo off
setlocal
title Anno 1503 crash collector
cd /d "%~dp0"
where py >nul 2>&1
if not errorlevel 1 goto use_py
where python >nul 2>&1
if not errorlevel 1 goto use_python
echo Python 3.10 or newer is required. See README.txt.
goto failed
:use_py
py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if errorlevel 1 goto failed
py -3 -u "%~dp0collect_crash.py" --game-dir "%~dp0.."
set "ANNOCRASH_RESULT=%ERRORLEVEL%"
goto done
:use_python
python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if errorlevel 1 goto failed
python -u "%~dp0collect_crash.py" --game-dir "%~dp0.."
set "ANNOCRASH_RESULT=%ERRORLEVEL%"
goto done
:failed
set "ANNOCRASH_RESULT=1"
echo ERROR: A working Python 3.10 or newer installation was not found.
:done
echo.
if "%ANNOCRASH_RESULT%"=="0" (echo Attach the newly created crash report ZIP in the chat.) else (echo Collection failed. Copy the ERROR line above.)
echo.
pause
exit /b %ANNOCRASH_RESULT%
