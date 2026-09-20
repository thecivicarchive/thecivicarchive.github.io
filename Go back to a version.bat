@echo off
title The Civic Archive - go back to a version
cd /d "%~dp0"
echo Saved versions, newest first:
echo.
".venv\Scripts\python.exe" version.py list
echo.
set /p V=Type the version to go back to (for example 4.0.001), or press Enter to cancel: 
if "%V%"=="" exit /b 0
".venv\Scripts\python.exe" version.py back %V%
echo.
pause
