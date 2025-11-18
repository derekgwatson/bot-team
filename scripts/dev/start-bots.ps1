# Base directory for all bots
$baseDir = 'C:\Users\Derek\Documents\Coding\Python_Scripts\bot-team'

# Folder names for each bot (these match the subfolders under bot-team)
$botFolders = @(
    'pam',
    'peter',
    'dorothy',
    'sally',
    'chester'
)

# Keep jobs in a global so you can stop them later in the same session
$global:BotJobs = @()

foreach ($folder in $botFolders) {
    # Capitalise the bot name for display / job name
    $displayName = $folder.Substring(0,1).ToUpper() + $folder.Substring(1)

    $workingDir = Join-Path $baseDir $folder
    $venvPython = Join-Path $workingDir '.venv\Scripts\python.exe'

    Write-Host "Starting $displayName ..."

    $job = Start-Job -Name $displayName -ScriptBlock {
        param($workingDir, $venvPython)

        # Make the job’s console / Python IO use UTF-8
        [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
        $env:PYTHONIOENCODING = 'utf-8'

        Set-Location $workingDir
        & $venvPython .\app.py
    } -ArgumentList $workingDir, $venvPython

    $global:BotJobs += $job
}

Write-Host "Bots started. Use 'Get-Job' to see status, 'Receive-Job -Name Pam' to view output, etc."


