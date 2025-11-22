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

# --- Get port from chester's config.yaml (single source of truth) ---
function Get-BotPort {
    param([string]$BotName)

    $pythonScript = @"
import sys
sys.path.insert(0, r'$baseDir')
from shared.config.ports import get_port
port = get_port('$BotName')
if port:
    print(port)
else:
    sys.exit(1)
"@

    $result = & $venvPython -c $pythonScript 2>&1
    if ($LASTEXITCODE -eq 0) {
        $portLine = $result | Where-Object { $_ -match '^\d+$' } | Select-Object -First 1
        if ($portLine) {
            return [int]$portLine
        }
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
        $port = Get-BotPort -BotName $botName
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
