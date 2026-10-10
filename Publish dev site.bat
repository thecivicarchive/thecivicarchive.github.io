@echo off
title The Civic Archive - publish the draft
cd /d "%~dp0"
echo Publishing the DRAFT site so others can look at it.
echo Your live site is not affected.
echo.
if not exist "site\dev\index.html" (
  echo No draft built yet. Run "Preview dev site.bat" first.
  echo.
  pause
  exit /b 1
)
if not exist "docs\dev" mkdir "docs\dev"
rem The published pages carry no names of the kit's own files and programs: one last pass before the copy.
rem The companion and the page guide ride on every page that keeps its own top bar.
".venv\Scripts\python.exe" build_shell.py --ride --root "site\dev"
".venv\Scripts\python.exe" quiet_pages.py "site\dev"
rem The companions' lab and test pages and the tab icons' lab are for checking things here; they are never published.
robocopy "site\dev" "docs\dev" /MIR /NFL /NDL /NJH /NJS /NP /XF _companion_lab.html companions.html _tabicons_lab.html >nul
if errorlevel 8 (
  echo Could not copy the draft. Is a file open in another program? Close it and retry.
  echo.
  pause
  exit /b 1
)
git add -A docs\dev
git diff --cached --quiet
if not errorlevel 1 (
  echo.
  echo The draft has not changed since last time. Nothing to publish.
  echo.
  pause
  exit /b 0
)
set "VER="
for /f "usebackq delims=" %%v in (`".venv\Scripts\python.exe" version.py current`) do set "VER=%%v"
git commit -q -m "Publish draft v%VER%"
echo Uploading ...
git push -q origin main
if errorlevel 1 (
  echo.
  echo Upload failed - check your internet connection and run this again.
  echo Your work is saved on this computer either way.
  echo.
  pause
  exit /b 1
)
echo.
echo Done. The draft is live in about a minute at:
echo   https://thecivicarchive.github.io/dev/
echo.
pause
