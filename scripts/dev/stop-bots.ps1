# Stop bot-team bots for local development
# Usage:
#   .\stop-bots.ps1           # Kill all Python processes (fast)
#   .\stop-bots.ps1 oscar     # Stop only oscar (by port)
#   .\stop-bots.ps1 oscar pam # Stop oscar and pam (by port)

param(
    [Parameter(ValueFromRemainingArguments=$true)]
    [string[]]$BotNames
)

# Base directory for all bots
$baseDir = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$venvPython = Join-Path $baseDir '.venv\Scripts\python.exe'

# --- Get port from a bot's config.yaml ---
function Get-BotPort {
    param([string]$BotDir)

    $configPath = Join-Path $BotDir 'config.yaml'
    if (-not (Test-Path $configPath)) {
        return $null
    }

    $pythonScript = @"
import yaml
import sys

try:
    with open(r'$configPath', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    port = data.get('server', {}).get('port')
    if port:
        print(port)
    else:
        sys.exit(1)
except Exception as e:
    sys.exit(1)
"@

    $result = & $venvPython -c $pythonScript 2>&1
    if ($LASTEXITCODE -eq 0) {
        return [int]$result
    }
    return $null
}

# --- Kill process on a specific port ---
function Stop-ProcessOnPort {
    param([int]$Port, [string]$BotName)

    $displayName = $BotName.Substring(0,1).ToUpper() + $BotName.Substring(1)

    try {
        $connection = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($connection) {
            $process = Get-Process -Id $connection.OwningProcess -ErrorAction SilentlyContinue
            if ($process) {
                Write-Host "  [KILL] $displayName on port $Port (PID: $($connection.OwningProcess))" -ForegroundColor Red
                Stop-Process -Id $connection.OwningProcess -Force -ErrorAction Stop
                return $true
            }
        }
    } catch {
        Write-Host "  [FAIL] $displayName - $($_.Exception.Message)" -ForegroundColor Yellow
    }

    Write-Host "  [SKIP] $displayName - not running on port $Port" -ForegroundColor Yellow
    return $false
}

# --- Main ---
if ($BotNames -and $BotNames.Count -gt 0) {
    # Stop specific bots by finding their ports
    Write-Host "Stopping specified bots: $($BotNames -join ', ')" -ForegroundColor Cyan
    Write-Host ""

    foreach ($botName in $BotNames) {
        $botDir = Join-Path $baseDir $botName
        $port = Get-BotPort -BotDir $botDir
        if ($port) {
            Stop-ProcessOnPort -Port $port -BotName $botName | Out-Null
        } else {
            Write-Host "  [SKIP] $botName - no port configured" -ForegroundColor Yellow
        }
    }
} else {
    # Kill ALL Python processes (fast and thorough)
    Write-Host "Killing all Python processes..." -ForegroundColor Cyan
    Write-Host ""

    $pythonProcesses = Get-Process python*, pythonw* -ErrorAction SilentlyContinue
    if ($pythonProcesses) {
        $count = $pythonProcesses.Count
        $pythonProcesses | Stop-Process -Force -ErrorAction SilentlyContinue
        Write-Host "  [KILL] Killed $count Python process(es)" -ForegroundColor Red
    } else {
        Write-Host "  [SKIP] No Python processes running" -ForegroundColor Yellow
    }
}

# Clear any stored jobs
$global:BotJobs = @{}

Write-Host ""
Write-Host "Done." -ForegroundColor Green
