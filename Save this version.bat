@echo off
title The Civic Archive - save this version
cd /d "%~dp0"
echo Saving this version of the site (nothing is uploaded) ...
echo.
".venv\Scripts\python.exe" version.py save
echo.
pause
