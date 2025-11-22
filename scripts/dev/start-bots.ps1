# Start bot-team bots for local development
# Usage:
#   .\start-bots.ps1           # Start all bots
#   .\start-bots.ps1 oscar     # Start only oscar
#   .\start-bots.ps1 oscar pam # Start oscar and pam

param(
    [Parameter(ValueFromRemainingArguments=$true)]
    [string[]]$BotNames
)

# Base directory for all bots
$baseDir = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$chesterConfig = Join-Path $baseDir 'chester\config.yaml'

# --- Load bot list dynamically from Chester's config.yaml ---
function Get-BotListFromYaml {
    param([string]$ConfigPath)

    $pythonScript = @"
import yaml
import sys

try:
    with open(r'$ConfigPath') as f:
        data = yaml.safe_load(f)
    bot_team = data.get('bot_team', {})
    for bot in bot_team.keys():
        print(bot)
except Exception as e:
    print(f'Error: {e}', file=sys.stderr)
    sys.exit(1)
"@

    $result = python -c $pythonScript 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to read bot list from config: $result" -ForegroundColor Red
        return @()
    }
    return $result -split "`n" | Where-Object { $_ -ne '' }
}

# Determine which bots to start
if ($BotNames -and $BotNames.Count -gt 0) {
    $botFolders = $BotNames
    Write-Host "Starting specified bots: $($botFolders -join ', ')" -ForegroundColor Cyan
} else {
    Write-Host "Loading bot list from Chester's config.yaml..." -ForegroundColor Cyan
    $botFolders = Get-BotListFromYaml -ConfigPath $chesterConfig
    if ($botFolders.Count -eq 0) {
        Write-Host "No bots found in config. Exiting." -ForegroundColor Red
        exit 1
    }
    Write-Host "Found $($botFolders.Count) bots: $($botFolders -join ', ')" -ForegroundColor Cyan
}

# Keep jobs in a global so you can stop them later in the same session
if (-not $global:BotJobs) {
    $global:BotJobs = @{}
}

Write-Host ""

foreach ($folder in $botFolders) {
    # Skip if bot directory doesn't exist
    $workingDir = Join-Path $baseDir $folder
    if (-not (Test-Path $workingDir)) {
        Write-Host "  [SKIP] $folder - directory not found" -ForegroundColor Yellow
        continue
    }

    # Check if already running
    if ($global:BotJobs.ContainsKey($folder) -and $global:BotJobs[$folder].State -eq 'Running') {
        Write-Host "  [SKIP] $folder - already running" -ForegroundColor Yellow
        continue
    }

    # Capitalise the bot name for display
    $displayName = $folder.Substring(0,1).ToUpper() + $folder.Substring(1)
    $venvPython = Join-Path $workingDir '.venv\Scripts\python.exe'

    # Check if venv exists
    if (-not (Test-Path $venvPython)) {
        Write-Host "  [SKIP] $folder - no .venv found" -ForegroundColor Yellow
        continue
    }

    Write-Host "  [START] $displayName ..." -ForegroundColor Green

    $job = Start-Job -Name $displayName -ScriptBlock {
        param($workingDir, $venvPython)

        # Make the job's console / Python IO use UTF-8
        [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
        $env:PYTHONIOENCODING = 'utf-8'

        Set-Location $workingDir
        & $venvPython .\app.py
    } -ArgumentList $workingDir, $venvPython

    $global:BotJobs[$folder] = $job
}

Write-Host ""
Write-Host "Bots started. Commands:" -ForegroundColor Cyan
Write-Host "  Get-Job                    # See status of all jobs"
Write-Host "  Receive-Job -Name Oscar    # View output from Oscar"
Write-Host "  .\stop-bots.ps1            # Stop all bots"
Write-Host "  .\stop-bots.ps1 oscar      # Stop just Oscar"
Write-Host ""
