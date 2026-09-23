@echo off
cd /d %~dp0
if not exist .venv (
  echo EMS virtual environment not found. Run START_WINDOWS.bat once first.
  exit /b 1
)
call .venv\Scripts\activate
python backup.py backup
