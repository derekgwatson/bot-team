Get-ChildItem -Directory | ForEach-Object {
    $venvPython = Join-Path $_.FullName '.venv\Scripts\python.exe'

    if (Test-Path $venvPython) {
        $pipVersionOutput = & $venvPython -m pip --version 2>$null

        if (-not $pipVersionOutput) {
            [PSCustomObject]@{
                Project    = $_.Name
                PipVersion = 'Unknown'
                LatestPip  = 'Unknown'
                UpToDate   = 'Could not query pip version'
            }
            return
        }

        $current = $pipVersionOutput.Split()[1]

        # Ask PyPI what the latest pip version is (requires reasonably recent pip + net)
        $indexOutput = & $venvPython -m pip index version pip 2>$null

        if ($LASTEXITCODE -ne 0 -or -not $indexOutput) {
            [PSCustomObject]@{
                Project    = $_.Name
                PipVersion = $current
                LatestPip  = 'Unknown'
                UpToDate   = 'Could not query (old pip/no net?)'
            }
        } else {
            $latest = (
                $indexOutput |
                Select-String -Pattern 'Latest:\s*([0-9\.]+)'
            ).Matches[0].Groups[1].Value

            [PSCustomObject]@{
                Project    = $_.Name
                PipVersion = $current
                LatestPip  = $latest
                UpToDate   = ($current -eq $latest)
            }
        }
    }
} | Format-Table -AutoSize
