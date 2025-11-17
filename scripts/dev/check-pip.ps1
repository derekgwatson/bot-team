Get-ChildItem -Directory | ForEach-Object {
    $venvPython = Join-Path $_.FullName '.venv\Scripts\python.exe'

    if (Test-Path $venvPython) {
        $current = (& $venvPython -m pip --version).Split()[1]

        # Ask PyPI what the latest pip version is (requires reasonably recent pip)
        $indexOutput = & $venvPython -m pip index version pip 2>$null

        if ($LASTEXITCODE -ne 0 -or -not $indexOutput) {
            [PSCustomObject]@{
                Project   = $_.Name
                PipVersion = $current
                LatestPip = 'Unknown'
                UpToDate  = 'Could not query (old pip/no net?)'
            }
        } else {
            $latest = (
                $indexOutput |
                Select-String -Pattern 'Latest:\s*([0-9\.]+)'
            ).Matches[0].Groups[1].Value

            [PSCustomObject]@{
                Project   = $_.Name
                PipVersion = $current
                LatestPip = $latest
                UpToDate  = ($current -eq $latest)
            }
        }
    }
} | Format-Table -AutoSize
