# Stop bot-team bots for local development
# Usage:
#   .\stop-bots.ps1           # Stop all bots
#   .\stop-bots.ps1 oscar     # Stop only oscar
#   .\stop-bots.ps1 oscar pam # Stop oscar and pam

param(
    [Parameter(ValueFromRemainingArguments=$true)]
    [string[]]$BotNames
)

function Stop-Bots {
    param(
        [string[]]$BotsToStop
    )

    if (-not $global:BotJobs -or $global:BotJobs.Count -eq 0) {
        Write-Host "No BotJobs found." -ForegroundColor Yellow
        return
    }

    # If specific bots requested, filter to just those
    if ($BotsToStop -and $BotsToStop.Count -gt 0) {
        Write-Host "Stopping specified bots: $($BotsToStop -join ', ')" -ForegroundColor Cyan
        Write-Host ""

        foreach ($botName in $BotsToStop) {
            if ($global:BotJobs.ContainsKey($botName)) {
                $job = $global:BotJobs[$botName]
                $displayName = $botName.Substring(0,1).ToUpper() + $botName.Substring(1)

                if ($job.State -eq 'Running') {
                    Write-Host "  [STOP] $displayName" -ForegroundColor Red
                    Stop-Job $job -Force
                } else {
                    Write-Host "  [SKIP] $displayName - not running (state: $($job.State))" -ForegroundColor Yellow
                }
                Remove-Job $job -Force -ErrorAction SilentlyContinue
                $global:BotJobs.Remove($botName)
            } else {
                Write-Host "  [SKIP] $botName - no job found" -ForegroundColor Yellow
            }
        }
    } else {
        # Stop all bots
        Write-Host "Stopping all bot jobs..." -ForegroundColor Cyan
        Write-Host ""

        foreach ($botName in @($global:BotJobs.Keys)) {
            $job = $global:BotJobs[$botName]
            $displayName = $botName.Substring(0,1).ToUpper() + $botName.Substring(1)

            if ($job.State -eq 'Running') {
                Write-Host "  [STOP] $displayName" -ForegroundColor Red
                Stop-Job $job -Force
            } else {
                Write-Host "  [CLEAN] $displayName (was $($job.State))" -ForegroundColor Gray
            }
            Remove-Job $job -Force -ErrorAction SilentlyContinue
        }

        $global:BotJobs = @{}
    }

    Write-Host ""
    Write-Host "Done." -ForegroundColor Green
}

# Run the function with any provided bot names
Stop-Bots -BotsToStop $BotNames
