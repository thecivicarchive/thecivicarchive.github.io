@echo off
title The Civic Archive - preview the draft
cd /d "%~dp0"
echo Building the draft site (this does NOT touch your live site) ...
echo.
if not exist "congress_119.sqlite" (
  echo No database yet. Run a full build first: python run_all.py
  echo.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" build_site_dev.py --db congress_119.sqlite --out "site\dev.html"
if errorlevel 1 (
  echo.
  echo The draft build failed. The message above says why.
  echo.
  pause
  exit /b 1
)
echo.
echo Opening the draft in your browser ...
start "" "site\dev.html"
echo.
echo This is a local preview only. Nobody else can see it.
echo To let others see it, use "Publish dev site.bat".
echo.
pause
