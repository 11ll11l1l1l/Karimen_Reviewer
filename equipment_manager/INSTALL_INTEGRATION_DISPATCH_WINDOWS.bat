@echo off
setlocal
cd /d %~dp0
set "TASK_NAME=EMS Integration Outbox"
set "SCRIPT=%~dp0RUN_INTEGRATIONS_WINDOWS.bat"
schtasks /Create /F /SC MINUTE /MO 5 /TN "%TASK_NAME%" /TR "\"%SCRIPT%\"" >nul
if errorlevel 1 (
  echo Could not create integration dispatcher scheduled task.
  exit /b 1
)
echo Created Windows scheduled task: %TASK_NAME%
echo Dispatcher cadence: every 5 minutes
