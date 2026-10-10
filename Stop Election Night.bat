@echo off
title Election Night - stop the updater
cd /d "%~dp0"
set "PYTHONIOENCODING=utf-8"
echo Asking Election Night's updater to finish what it is doing, publish "updates paused" and stop ...
echo.
".venv\Scripts\python.exe" run_night.py stop
echo.
pause
