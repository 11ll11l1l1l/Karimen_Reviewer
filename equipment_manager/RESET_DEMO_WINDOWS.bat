@echo off
cd /d %~dp0

echo Resetting isolated EMS demo data...
if exist equipment_manager_demo.db del /f /q equipment_manager_demo.db
if exist demo_files rmdir /s /q demo_files

call START_DEMO_WINDOWS.bat
