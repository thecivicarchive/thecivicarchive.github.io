@echo off
title Election Night - Minnesota's results folder
cd /d "%~dp0"
set "PYTHONIOENCODING=utf-8"
".venv\Scripts\python.exe" run_night.py folder mn --open
if errorlevel 1 (
  if not exist "states_cache\mn_local\sos\20261103\results" mkdir "states_cache\mn_local\sos\20261103\results"
  start "" explorer "states_cache\mn_local\sos\20261103\results"
)
echo.
echo On election night, save every text file from the Secretary of State's Media Files page into this
echo folder, every 15 to 30 minutes from about 8:15 p.m. until the counties finish, and once more in
echo the morning. Any file name is fine: the updater reads each file by what is in it, and when your
echo browser saves a file again under a new name, such as one ending in (1), it reads the newest copy.
echo.
pause
