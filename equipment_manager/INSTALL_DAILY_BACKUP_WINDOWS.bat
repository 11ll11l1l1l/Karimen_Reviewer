@echo off
setlocal
cd /d %~dp0
set "TASK_NAME=EMS Daily Database Backup"
set "BACKUP_CMD=%~dp0BACKUP_WINDOWS.bat"
schtasks /Create /F /SC DAILY /ST 02:00 /TN "%TASK_NAME%" /TR "\"%BACKUP_CMD%\"" >nul
if errorlevel 1 (
  echo Could not create scheduled task. Run this file with an account allowed to create scheduled tasks.
  exit /b 1
)
echo Created Windows scheduled task: %TASK_NAME%
echo Daily backup time: 02:00
echo The task runs BACKUP_WINDOWS.bat using the environment of the scheduled-task account.
