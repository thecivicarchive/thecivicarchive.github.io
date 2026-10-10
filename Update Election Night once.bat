@echo off
title Election Night - one update
cd /d "%~dp0"
set "PYTHONIOENCODING=utf-8"
echo Reading everything once, writing one set of figures and publishing them ...
echo (Use this in the days before election night. On the night itself, use "Start Election Night.bat".)
echo.
".venv\Scripts\python.exe" run_night.py once --publish
echo.
pause
