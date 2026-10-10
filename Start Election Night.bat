@echo off
title Election Night - the updater (keep this window open)
cd /d "%~dp0"
set "PYTHONIOENCODING=utf-8"
if not exist ".venv\Scripts\python.exe" (
  echo The kit's private Python is missing. Run "python run_all.py check" once, then try again.
  echo.
  pause
  exit /b 1
)
echo Election Night: starting the updater.
echo It reads the states' own results, picks up the files you save, writes new figures every 10 minutes
echo on election night and publishes them. Keep this window open, and keep the computer plugged in,
echo online and with its lid open. The computer is asked not to sleep while this window is open;
echo none of its settings is changed.
echo.
".venv\Scripts\python.exe" run_night.py live
echo.
echo Election Night's updater has stopped. Double-click "Start Election Night.bat" to start it again;
echo it carries on from where it stopped.
echo.
pause
