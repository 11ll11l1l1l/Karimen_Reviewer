param(
    [string]$RepoUrl = "https://github.com/11ll11l1l1l/Karimen_Reviewer.git",
    [string]$Branch = "main"
)

$ErrorActionPreference = "Stop"
$Source = Split-Path -Parent $MyInvocation.MyCommand.Path
$Work = Join-Path $env:TEMP "Karimen_Reviewer_v52_deploy"

if (Test-Path $Work) { Remove-Item -Recurse -Force $Work }
Write-Host "Cloning $RepoUrl ..."
git clone --branch $Branch $RepoUrl $Work

Write-Host "Copying Japan Driving License Exam Reviewer v5.2 ..."
$null = robocopy $Source $Work /E /XD .git __pycache__ /XF *.pyc *.v51bak deploy_to_github.ps1 deploy_to_github.sh
if ($LASTEXITCODE -gt 7) { throw "Robocopy failed with exit code $LASTEXITCODE" }

Push-Location $Work
try {
    git add -A
    $changes = git status --porcelain
    if (-not $changes) {
        Write-Host "No Git changes detected. Repository already matches this package."
        exit 0
    }
    git commit -m "Upgrade Japan Driving License Exam Reviewer to v5.2"
    git push origin $Branch
    Write-Host "v5.2 pushed successfully to $Branch."
    Write-Host "Next: check GitHub Actions / Streamlit deployment, then run supabase_setup.sql once if player_profiles does not exist."
}
finally {
    Pop-Location
}
