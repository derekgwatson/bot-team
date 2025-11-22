# Stop bot-team bots for local development
# Usage:
#   .\stop-bots.ps1           # Stop all bots
#   .\stop-bots.ps1 oscar     # Stop only oscar
#   .\stop-bots.ps1 oscar pam # Stop oscar and pam

param(
    [Parameter(ValueFromRemainingArguments=$true)]
    [string[]]$BotNames
)

# Base directory for all bots
$baseDir = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$chesterConfig = Join-Path $baseDir 'chester\config.yaml'
$venvPython = Join-Path $baseDir '.venv\Scripts\python.exe'

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
        return @()
    }
    return $result -split "`n" | Where-Object { $_ -ne '' }
}

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
    with open(r'$configPath') as f:
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

# --- Check if a port is in use and get the process ---
function Get-PortProcess {
    param([int]$Port)

    try {
        $connection = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($connection) {
            $process = Get-Process -Id $connection.OwningProcess -ErrorAction SilentlyContinue
            return @{
                InUse = $true
                ProcessId = $connection.OwningProcess
                ProcessName = $process.ProcessName
            }
        }
    } catch {}
    return @{ InUse = $false }
}

# --- Stop a single bot (job + orphaned process) ---
function Stop-SingleBot {
    param(
        [string]$BotName,
        [string]$BaseDir
    )

    $displayName = $BotName.Substring(0,1).ToUpper() + $BotName.Substring(1)
    $botDir = Join-Path $BaseDir $BotName
    $stopped = $false

    # Try to stop the job if it exists
    if ($global:BotJobs -and $global:BotJobs.ContainsKey($BotName)) {
        $job = $global:BotJobs[$BotName]
        if ($job.State -eq 'Running') {
            Write-Host "  [STOP] $displayName (job)" -ForegroundColor Red
            Stop-Job $job
            $stopped = $true
        }
        Remove-Job $job -Force -ErrorAction SilentlyContinue
        $global:BotJobs.Remove($BotName)
    }

    # Also check for orphaned process on the port
    if (Test-Path $botDir) {
        $port = Get-BotPort -BotDir $botDir
        if ($port) {
            $portInfo = Get-PortProcess -Port $port
            if ($portInfo.InUse) {
                Write-Host "  [KILL] $displayName - killing $($portInfo.ProcessName) on port $port (PID: $($portInfo.ProcessId))" -ForegroundColor Red
                Stop-Process -Id $portInfo.ProcessId -Force -ErrorAction SilentlyContinue
                $stopped = $true
            }
        }
    }

    if (-not $stopped) {
        Write-Host "  [SKIP] $displayName - not running" -ForegroundColor Yellow
    }
}

# --- Main stop function ---
function Stop-Bots {
    param(
        [string[]]$BotsToStop
    )

    # Determine which bots to stop
    if ($BotsToStop -and $BotsToStop.Count -gt 0) {
        $botList = $BotsToStop
        Write-Host "Stopping specified bots: $($botList -join ', ')" -ForegroundColor Cyan
    } else {
        # Get all bots from config
        $botList = Get-BotListFromYaml -ConfigPath $chesterConfig
        if ($botList.Count -eq 0) {
            Write-Host "No bots found in config." -ForegroundColor Yellow
            return
        }
        Write-Host "Stopping all bots..." -ForegroundColor Cyan
    }

    Write-Host ""

    foreach ($botName in $botList) {
        Stop-SingleBot -BotName $botName -BaseDir $baseDir
    }

    # Clear the jobs hashtable if stopping all
    if (-not $BotsToStop -or $BotsToStop.Count -eq 0) {
        $global:BotJobs = @{}
    }

    Write-Host ""
    Write-Host "Done." -ForegroundColor Green
}

# Run the function with any provided bot names
Stop-Bots -BotsToStop $BotNames
