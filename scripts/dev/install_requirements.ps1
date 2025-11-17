Get-ChildItem -Directory | ForEach-Object {
    $project    = $_.Name
    $root       = $_.FullName
    $venvPython = Join-Path $root ".venv\Scripts\python.exe"
    $reqFile    = Join-Path $root "requirements.txt"

    if ((Test-Path $venvPython) -and (Test-Path $reqFile)) {
        Write-Host "=== $($project): installing from requirements.txt ===" -ForegroundColor Cyan
        & $venvPython -m pip install -r $reqFile
    }
    elseif (-not (Test-Path $venvPython)) {
        Write-Host "Skipping $($project) (no .venv found)" -ForegroundColor DarkYellow
    }
    elseif (-not (Test-Path $reqFile)) {
        Write-Host "Skipping $($project) (no requirements.txt)" -ForegroundColor DarkYellow
    }
}
