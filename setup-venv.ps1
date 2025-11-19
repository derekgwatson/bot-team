# Setup script for consolidated virtual environment (PowerShell)

Write-Host "Setting up consolidated virtual environment for bot-team" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

# Navigate to project root
Set-Location $PSScriptRoot

# Create virtual environment at root if it doesn't exist
if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment at project root..." -ForegroundColor Yellow
    python -m venv .venv
    Write-Host "Virtual environment created" -ForegroundColor Green
}
else {
    Write-Host "Virtual environment already exists at project root" -ForegroundColor Blue
}

Write-Host ""
Write-Host "Installing dependencies..." -ForegroundColor Yellow
& .\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt

Write-Host ""
Write-Host "Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "To activate the virtual environment:" -ForegroundColor Cyan
Write-Host "  .venv\Scripts\Activate.ps1" -ForegroundColor White
Write-Host ""
Write-Host "To clean up old bot-level venvs (optional):" -ForegroundColor Cyan
Write-Host "  Remove-Item -Recurse -Force chester\.venv, dorothy\.venv, sally\.venv" -ForegroundColor White
Write-Host "  Remove-Item -Recurse -Force fred\.venv, iris\.venv, peter\.venv, pam\.venv" -ForegroundColor White
Write-Host "  Remove-Item -Recurse -Force quinn\.venv, zac\.venv, olive\.venv, oscar\.venv, rita\.venv, sadie\.venv" -ForegroundColor White
Write-Host ""
