@echo off
cd /d %~dp0
if not exist .venv (
  echo EMS virtual environment not found. Run START_WINDOWS.bat once first.
  exit /b 1
)
call .venv\Scripts\activate
set /p BACKUP_PATH=Enter backup file path:
python recovery.py "%BACKUP_PATH%"
pause
