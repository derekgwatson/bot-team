Get-ChildItem -Directory | Select-Object `
    Name, `
    @{Name='HasVenv';Expression={ Test-Path (Join-Path $_.FullName '.venv') }} `
| Format-Table -AutoSize
