$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -r requirements-build.txt
python -m PyInstaller --clean --noconfirm ems.spec

$version = (python -c "from version import __version__; print(__version__)").Trim()
$packageRoot = Join-Path $PSScriptRoot ("dist\EMS-" + $version)
if (Test-Path $packageRoot) { Remove-Item -Recurse -Force $packageRoot }
New-Item -ItemType Directory -Path $packageRoot | Out-Null
Copy-Item "dist\EMS.exe" $packageRoot
Copy-Item "config.example.toml" $packageRoot
Copy-Item "PRODUCTION_DEPLOYMENT.md" $packageRoot
Copy-Item "README.md" $packageRoot

@"
@echo off
cd /d %~dp0
EMS.exe --preflight
if errorlevel 1 (
  echo EMS preflight failed.
  pause
  exit /b 1
)
EMS.exe
"@ | Set-Content -Encoding ASCII (Join-Path $packageRoot "START_EMS.bat")

@"
@echo off
cd /d %~dp0
EMS.exe --preflight
pause
"@ | Set-Content -Encoding ASCII (Join-Path $packageRoot "PREFLIGHT_EMS.bat")

Compress-Archive -Path "$packageRoot\*" -DestinationPath ("dist\EMS-Windows-" + $version + ".zip") -Force
Write-Host "Built dist\EMS-Windows-$version.zip"
