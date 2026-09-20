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
".venv\Scripts\python.exe" build_site_dev.py --db congress_119.sqlite --out "site\dev.html" --split "site\dev"
if errorlevel 1 (
  echo.
  echo The draft build failed. The message above says why.
  echo.
  pause
  exit /b 1
)
echo.
echo Starting a small local web server for the preview. A second window opens for it;
echo close that window when you are done looking.
start "The Civic Archive - preview server (close me when done)" ".venv\Scripts\python.exe" -m http.server 8790 --bind 127.0.0.1 --directory "site\dev"
timeout /t 2 /nobreak >nul
start "" "http://127.0.0.1:8790/"
echo.
echo The draft is open in your browser at http://127.0.0.1:8790/
echo This is a local preview only. Nobody else can see it.
echo The one-file copy is at site\dev.html (opens from a double-click, slower).
echo To let others see it, use "Publish dev site.bat".
echo.
pause
