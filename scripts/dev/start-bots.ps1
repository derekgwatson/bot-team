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
$venvPython = Join-Path $baseDir '.venv\Scripts\python.exe'

# Check shared venv exists
if (-not (Test-Path $venvPython)) {
    Write-Host "Shared venv not found at: $venvPython" -ForegroundColor Red
    Write-Host "Run 'python -m venv .venv' in $baseDir first." -ForegroundColor Yellow
    exit 1
}

# --- Load bot list dynamically from Chester's config.yaml ---
function Get-BotListFromYaml {
    param([string]$ConfigPath)

    $pythonScript = @"
import yaml
import sys

try:
    with open(r'$ConfigPath', encoding='utf-8') as f:
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
        print('NO_PORT', file=sys.stderr)
        sys.exit(1)
except Exception as e:
    print(f'ERROR: {e}', file=sys.stderr)
    sys.exit(1)
"@

    $result = & $venvPython -c $pythonScript 2>&1
    if ($LASTEXITCODE -eq 0) {
        # Filter out any stderr that leaked through
        $portLine = $result | Where-Object { $_ -match '^\d+$' } | Select-Object -First 1
        if ($portLine) {
            return [int]$portLine
        }
    }
    return $null
}

# --- Check if a port is in use and get the process ---
function Get-PortProcess {
    param([int]$Port)

    try {
        # Only look for LISTEN state - ignore TIME_WAIT, CLOSE_WAIT etc from dead processes
        $connection = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($connection) {
            # Verify the process actually exists (Windows can have stale TCP entries)
            $process = Get-Process -Id $connection.OwningProcess -ErrorAction SilentlyContinue
            if ($process) {
                return @{
                    InUse = $true
                    ProcessId = $connection.OwningProcess
                    ProcessName = $process.ProcessName
                }
            }
            # Process doesn't exist - stale TCP entry, ignore it
        }
    } catch {}
    return @{ InUse = $false }
}

# --- Check bot health endpoint ---
function Test-BotHealth {
    param(
        [string]$BotName,
        [int]$Port,
        [int]$TimeoutSeconds = 5
    )

    try {
        $response = Invoke-WebRequest -Uri "http://localhost:$Port/health" -TimeoutSec $TimeoutSeconds -UseBasicParsing -ErrorAction Stop
        return @{ Success = $true; StatusCode = $response.StatusCode }
    } catch {
        return @{ Success = $false; Error = $_.Exception.Message }
    }
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

$startedBots = @()

foreach ($folder in $botFolders) {
    # Skip if bot directory doesn't exist
    $workingDir = Join-Path $baseDir $folder
    if (-not (Test-Path $workingDir)) {
        Write-Host "  [SKIP] $folder - directory not found" -ForegroundColor Yellow
        continue
    }

    # Check if already running (known job)
    if ($global:BotJobs.ContainsKey($folder) -and $global:BotJobs[$folder].State -eq 'Running') {
        Write-Host "  [SKIP] $folder - already running" -ForegroundColor Yellow
        continue
    }

    # Capitalise the bot name for display
    $displayName = $folder.Substring(0,1).ToUpper() + $folder.Substring(1)

    # Get port and check if it's already in use (orphaned process)
    $port = Get-BotPort -BotDir $workingDir
    if ($port) {
        $portInfo = Get-PortProcess -Port $port
        if ($portInfo.InUse) {
            Write-Host "  [SKIP] $displayName - port $port already in use by $($portInfo.ProcessName) (PID: $($portInfo.ProcessId))" -ForegroundColor Yellow
            Write-Host "         Run: Stop-Process -Id $($portInfo.ProcessId) -Force" -ForegroundColor Gray
            continue
        }
    }

    Write-Host "  [START] $displayName ..." -ForegroundColor Green

    $job = Start-Job -Name $displayName -ScriptBlock {
        param($workingDir, $venvPython)

        # Make the job's console / Python IO use UTF-8
        [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
        $env:PYTHONIOENCODING = 'utf-8'

        Set-Location $workingDir
        # Redirect stderr to stdout so we capture error messages
        & $venvPython .\app.py 2>&1
    } -ArgumentList $workingDir, $venvPython

    $global:BotJobs[$folder] = $job
    $startedBots += $folder
}

# --- Health check after startup ---
if ($startedBots.Count -gt 0) {
    Write-Host ""
    Write-Host "Waiting 5 seconds for bots to initialize..." -ForegroundColor Cyan
    Start-Sleep -Seconds 5

    Write-Host ""
    Write-Host "Checking health endpoints..." -ForegroundColor Cyan
    Write-Host ""

    $healthy = @()
    $unhealthy = @()

    foreach ($bot in $startedBots) {
        $botDir = Join-Path $baseDir $bot
        $port = Get-BotPort -BotDir $botDir
        $displayName = $bot.Substring(0,1).ToUpper() + $bot.Substring(1)

        if (-not $port) {
            # Try to get more info about why port detection failed
            $botConfigPath = Join-Path $botDir 'config.yaml'
            $debugResult = & $venvPython -c "import yaml; print(yaml.safe_load(open(r'$botConfigPath', encoding='utf-8')).get('server', {}))" 2>&1
            Write-Host "  [WARN] $displayName - no port in config (debug: $debugResult)" -ForegroundColor Yellow
            $unhealthy += $bot
            continue
        }

        # Check if job is still running
        $job = $global:BotJobs[$bot]
        if ($job.State -ne 'Running') {
            Write-Host "  [FAIL] $displayName - job not running (state: $($job.State))" -ForegroundColor Red
            # Show error output if available
            $output = Receive-Job $job -ErrorAction SilentlyContinue
            if ($output) {
                Write-Host "         Output: $($output | Select-Object -Last 3)" -ForegroundColor Gray
            }
            $unhealthy += $bot
            continue
        }

        # Check health endpoint
        $healthResult = Test-BotHealth -BotName $bot -Port $port
        if ($healthResult.Success) {
            Write-Host "  [OK]   $displayName (port $port)" -ForegroundColor Green
            $healthy += $bot
        } else {
            Write-Host "  [FAIL] $displayName (port $port) - $($healthResult.Error)" -ForegroundColor Red
            # Show job output to help diagnose why it failed
            $output = Receive-Job $job -Keep -ErrorAction SilentlyContinue 2>&1
            if ($output) {
                Write-Host "         Recent output:" -ForegroundColor Gray
                $output | Select-Object -Last 5 | ForEach-Object {
                    Write-Host "           $_" -ForegroundColor Gray
                }
            }
            $unhealthy += $bot
        }
    }

    Write-Host ""
    if ($unhealthy.Count -gt 0) {
        Write-Host "WARNING: $($unhealthy.Count) bot(s) failed to start: $($unhealthy -join ', ')" -ForegroundColor Red
        Write-Host "Use 'Receive-Job -Name BotName' to see error output" -ForegroundColor Yellow
    } else {
        Write-Host "All $($healthy.Count) bot(s) started successfully!" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "Commands:" -ForegroundColor Cyan
Write-Host "  Get-Job                    # See status of all jobs"
Write-Host "  Receive-Job -Name Oscar    # View output from Oscar"
Write-Host "  .\stop-bots.ps1            # Stop all bots"
Write-Host "  .\stop-bots.ps1 oscar      # Stop just Oscar"
Write-Host ""
