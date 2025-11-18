function Stop-Bots {
    if (-not $global:BotJobs -or $global:BotJobs.Count -eq 0) {
        Write-Host "No BotJobs found."
        return
    }

    Write-Host "Stopping all bot jobs..."
    $global:BotJobs | ForEach-Object {
        if ($_.State -eq 'Running') {
            Stop-Job $_ -Force
        }
        Remove-Job $_
    }

    $global:BotJobs = @()
    Write-Host "All bot jobs stopped."
}
