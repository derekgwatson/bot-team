# start-bots.ps1

$bots = @(
    @{
        Name       = 'Pam'
        WorkingDir = 'C:\Users\Derek\Documents\Coding\Python_Scripts\bot-team\pam'
        VenvPython = 'C:\Users\Derek\Documents\Coding\Python_Scripts\bot-team\pam\.venv\Scripts\python.exe'
    },
    @{
        Name       = 'Peter'
        WorkingDir = 'C:\Users\Derek\Documents\Coding\Python_Scripts\bot-team\peter'
        VenvPython = 'C:\Users\Derek\Documents\Coding\Python_Scripts\bot-team\peter\.venv\Scripts\python.exe'
    },
    @{
        Name       = 'Dorothy'
        WorkingDir = 'C:\Users\Derek\Documents\Coding\Python_Scripts\bot-team\dorothy'
        VenvPython = 'C:\Users\Derek\Documents\Coding\Python_Scripts\bot-team\dorothy\.venv\Scripts\python.exe'
    }
)

# Keep jobs in a global so you can stop them later in the same session
$global:BotJobs = @()

foreach ($bot in $bots) {
    Write-Host "Starting $($bot.Name) ..."

    $job = Start-Job -Name $bot.Name -ScriptBlock {
        param($workingDir, $venvPython)

        Set-Location $workingDir

        # If you prefer, you can do: & python .\app.py
        # but using the venv's python is cleaner
        & $venvPython .\app.py
    } -ArgumentList $bot.WorkingDir, $bot.VenvPython

    $global:BotJobs += $job
}

Write-Host "Bots started. Use 'Get-Job' to see status, 'Receive-Job -Name Pam' to view output, etc."
